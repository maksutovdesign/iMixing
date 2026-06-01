from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class LoudnessMetrics:
    integrated_lufs: float
    true_peak_dbtp: float
    sample_peak_dbfs: float
    method: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def analyze_loudness(audio, sample_rate: int, np) -> LoudnessMetrics:
    sample_peak = _peak_db(audio, np)
    true_peak = _true_peak_db(audio, np)

    try:
        import pyloudnorm as pyln
    except ImportError:
        return LoudnessMetrics(
            integrated_lufs=round(_rms_loudness(audio, np), 2),
            true_peak_dbtp=round(true_peak, 2),
            sample_peak_dbfs=round(sample_peak, 2),
            method="rms-fallback",
        )

    meter = pyln.Meter(sample_rate)
    integrated = float(meter.integrated_loudness(audio))
    return LoudnessMetrics(
        integrated_lufs=round(integrated, 2),
        true_peak_dbtp=round(true_peak, 2),
        sample_peak_dbfs=round(sample_peak, 2),
        method="pyloudnorm",
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
    oversampled = _oversample_linear(audio, np, factor=4)
    return _peak_db(oversampled, np)


def _oversample_linear(audio, np, *, factor: int):
    if factor <= 1 or len(audio) < 2:
        return audio

    sample_count = audio.shape[0]
    source = np.arange(sample_count)
    target = np.linspace(0, sample_count - 1, sample_count * factor)
    channels = []
    for channel in range(audio.shape[1]):
        channels.append(np.interp(target, source, audio[:, channel]))
    return np.column_stack(channels)
