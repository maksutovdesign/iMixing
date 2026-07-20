from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class LoudnessMetrics:
    integrated_lufs: float
    true_peak_dbtp: float
    sample_peak_dbfs: float
    short_term_max_lufs: float | None
    loudness_range_lu: float | None
    crest_factor_db: float
    method: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def analyze_loudness(audio, sample_rate: int, np) -> LoudnessMetrics:
    sample_peak = _peak_db(audio, np)
    true_peak = _true_peak_db(audio, np)
    crest_factor = sample_peak - _rms_loudness(audio, np)

    try:
        import pyloudnorm as pyln
    except ImportError:
        integrated = _rms_loudness(audio, np)
        return LoudnessMetrics(
            integrated_lufs=round(integrated, 2),
            true_peak_dbtp=round(true_peak, 2),
            sample_peak_dbfs=round(sample_peak, 2),
            short_term_max_lufs=round(_max_window_rms_loudness(audio, sample_rate, np), 2),
            loudness_range_lu=round(_window_loudness_range(audio, sample_rate, np), 2),
            crest_factor_db=round(crest_factor, 2),
            method="rms-fallback (install pyloudnorm for BS.1770 loudness)",
        )

    meter = pyln.Meter(sample_rate)
    integrated = float(meter.integrated_loudness(audio))
    short_term_values = _short_term_loudness(audio, sample_rate, meter, np)
    return LoudnessMetrics(
        integrated_lufs=round(integrated, 2),
        true_peak_dbtp=round(true_peak, 2),
        sample_peak_dbfs=round(sample_peak, 2),
        short_term_max_lufs=round(max(short_term_values), 2) if short_term_values else None,
        loudness_range_lu=round(_percentile_range(short_term_values, np), 2) if short_term_values else None,
        crest_factor_db=round(crest_factor, 2),
        method="BS.1770 via pyloudnorm; true peak 4x oversampled",
    )


def target_lufs(target: str) -> float:
    compact = target.lower().replace(" ", "")
    if "-8lufs" in compact:
        return -8.0
    if "-9lufs" in compact:
        return -9.0
    if "-10lufs" in compact:
        return -10.0
    if "-11lufs" in compact:
        return -11.0
    if "-12lufs" in compact:
        return -12.0
    if "-16lufs" in compact:
        return -16.0
    return -14.0


def target_true_peak_dbtp(target: str) -> float:
    """Read an optional dBTP ceiling from the public target string."""
    compact = target.lower().replace(" ", "")
    for value in (-0.3, -0.5, -0.8, -1.0, -1.5, -2.0):
        marker = f"{value:g}dbtp"
        if marker in compact:
            return value
    return -1.0


def gain_to_lufs(audio, sample_rate: int, target: str, np) -> tuple[float, LoudnessMetrics]:
    metrics = analyze_loudness(audio, sample_rate, np)
    gain_db = target_lufs(target) - metrics.integrated_lufs
    true_peak_limited_gain = -1.0 - metrics.true_peak_dbtp
    return max(-12.0, min(gain_db, true_peak_limited_gain, 9.0)), metrics


def _rms_loudness(audio, np) -> float:
    rms = float(np.sqrt(np.mean(np.square(audio))) + 1e-12)
    return 20.0 * math.log10(rms)


def _peak_db(audio, np) -> float:
    peak = float(np.max(np.abs(audio)))
    if peak <= 0:
        return -120.0
    return 20.0 * math.log10(peak)


def _true_peak_db(audio, np) -> float:
    oversampled = _oversample_true_peak(audio, np, factor=4)
    return _peak_db(oversampled, np)


def _oversample_true_peak(audio, np, *, factor: int):
    """Use a band-limited resampler when available; do not call linear interpolation true peak."""
    if factor <= 1 or len(audio) < 2:
        return audio

    try:
        from scipy.signal import resample_poly

        return resample_poly(audio, up=factor, down=1, axis=0, window=("kaiser", 8.6))
    except ImportError:
        # A conservative fallback: never claim an interpolated value is BS.1770 true peak.
        return audio


def _short_term_loudness(audio, sample_rate: int, meter, np) -> list[float]:
    window = max(1, int(sample_rate * 3))
    hop = max(1, int(sample_rate))
    if len(audio) < max(1, int(sample_rate * 0.4)):
        return []
    values = []
    for start in range(0, max(1, len(audio) - window + 1), hop):
        chunk = audio[start : start + window]
        if len(chunk) < int(sample_rate * 0.4):
            continue
        try:
            values.append(float(meter.integrated_loudness(chunk)))
        except ValueError:
            continue
    return values


def _max_window_rms_loudness(audio, sample_rate: int, np) -> float:
    values = _window_rms_loudness(audio, sample_rate, np)
    return max(values) if values else _rms_loudness(audio, np)


def _window_loudness_range(audio, sample_rate: int, np) -> float:
    return _percentile_range(_window_rms_loudness(audio, sample_rate, np), np)


def _window_rms_loudness(audio, sample_rate: int, np) -> list[float]:
    window = max(1, int(sample_rate * 3))
    hop = max(1, int(sample_rate))
    values = []
    for start in range(0, max(1, len(audio) - window + 1), hop):
        chunk = audio[start : start + window]
        if len(chunk):
            values.append(_rms_loudness(chunk, np))
    return values


def _percentile_range(values: list[float], np) -> float:
    if len(values) < 2:
        return 0.0
    return float(np.percentile(values, 95) - np.percentile(values, 10))
