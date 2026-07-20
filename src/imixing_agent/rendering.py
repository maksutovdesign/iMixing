from __future__ import annotations

import math
import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .loudness import LoudnessMetrics, analyze_loudness, target_lufs, target_true_peak_dbtp
from .models import MixProject, StemPlan


@dataclass(frozen=True)
class RenderResult:
    master_path: Path
    rough_mix_path: Path
    preview_path: Path | None
    warnings: list[str]
    genre: str
    premaster_loudness: LoudnessMetrics
    master_loudness: LoudnessMetrics
    quality_report: dict[str, Any]


ROLE_RENDER_SETTINGS: dict[str, dict[str, Any]] = {
    "kick": {
        "gain_db": 0.0,
        "target_rms_dbfs": -20.0,
        "pan": 0.0,
        "highpass_hz": 28.0,
        "lowpass_hz": 14000.0,
        "compressor": (-18.0, 4.0),
    },
    "snare": {
        "gain_db": 0.0,
        "target_rms_dbfs": -22.0,
        "pan": 0.0,
        "highpass_hz": 90.0,
        "eq": [("peak", 450.0, -1.5, 1.0), ("high_shelf", 7000.0, 0.8, 0.707)],
        "compressor": (-20.0, 3.0),
        "reverb": 0.035,
    },
    "drums": {
        "gain_db": 0.0,
        "target_rms_dbfs": -21.0,
        "pan": 0.0,
        "highpass_hz": 32.0,
        "eq": [("low_shelf", 90.0, -0.8, 0.707), ("high_shelf", 8000.0, -0.8, 0.707)],
        "compressor": (-18.0, 2.6),
    },
    "bass": {
        "gain_db": 0.0,
        "target_rms_dbfs": -22.5,
        "pan": 0.0,
        "highpass_hz": 34.0,
        "lowpass_hz": 5200.0,
        "eq": [("low_shelf", 95.0, -1.2, 0.707), ("peak", 220.0, -1.0, 1.0)],
        "compressor": (-22.0, 3.8),
    },
    "lead_vocal": {
        "gain_db": 0.0,
        "target_rms_dbfs": -18.5,
        "pan": 0.0,
        "highpass_hz": 95.0,
        "eq": [("peak", 300.0, -1.8, 1.0), ("peak", 2600.0, 1.0, 0.9), ("high_shelf", 7500.0, 0.9, 0.707)],
        "compressor": (-24.0, 2.8),
        "reverb": 0.045,
    },
    "backing_vocals": {
        "gain_db": 0.0,
        "target_rms_dbfs": -23.5,
        "pan": 0.35,
        "highpass_hz": 130.0,
        "eq": [("peak", 320.0, -1.5, 1.0), ("high_shelf", 7200.0, 0.6, 0.707)],
        "compressor": (-24.0, 2.3),
        "reverb": 0.065,
    },
    "guitar": {
        "gain_db": 0.0,
        "target_rms_dbfs": -23.5,
        "pan": -0.25,
        "highpass_hz": 90.0,
        "eq": [("peak", 350.0, -1.4, 1.0), ("high_shelf", 6500.0, 0.5, 0.707)],
        "compressor": (-21.0, 2.0),
    },
    "keys": {
        "gain_db": 0.0,
        "target_rms_dbfs": -24.0,
        "pan": 0.18,
        "highpass_hz": 115.0,
        "eq": [("low_shelf", 180.0, -1.6, 0.707), ("peak", 420.0, -1.0, 1.0)],
        "compressor": (-23.0, 1.8),
    },
    "synth": {
        "gain_db": 0.0,
        "target_rms_dbfs": -24.5,
        "pan": 0.25,
        "highpass_hz": 85.0,
        "eq": [("low_shelf", 180.0, -1.4, 0.707), ("high_shelf", 8500.0, 0.4, 0.707)],
        "compressor": (-22.0, 1.9),
    },
    "fx": {
        "gain_db": 0.0,
        "target_rms_dbfs": -29.0,
        "pan": 0.0,
        "highpass_hz": 140.0,
        "reverb": 0.08,
    },
    "other": {
        "gain_db": 0.0,
        "target_rms_dbfs": -28.0,
        "pan": 0.0,
        "highpass_hz": 110.0,
        "eq": [("low_shelf", 220.0, -2.0, 0.707)],
        "compressor": (-23.0, 1.7),
        "max_gain_db": 0.0,
    },
}


AUDIO_GENRE_PRESETS: dict[str, dict[str, Any]] = {
    "balanced": {
        "label": "Balanced",
        "premaster_peak_dbfs": -6.0,
        "role_gain_offsets": {},
    },
    "pop": {
        "label": "Pop",
        "premaster_peak_dbfs": -6.0,
        "role_gain_offsets": {"lead_vocal": 1.4, "backing_vocals": 0.4, "bass": 0.4, "fx": -0.6},
    },
    "vocal_louder": {
        "label": "Vocal Louder",
        "premaster_peak_dbfs": -6.0,
        "role_gain_offsets": {"lead_vocal": 2.2, "drums": -0.5, "bass": -0.4, "keys": -0.7, "other": -1.2},
    },
    "rap": {
        "label": "Rap",
        "premaster_peak_dbfs": -5.5,
        "role_gain_offsets": {"kick": 1.0, "drums": 0.8, "bass": 1.3, "lead_vocal": 1.0, "keys": -0.7, "synth": -0.5},
    },
    "rock": {
        "label": "Rock",
        "premaster_peak_dbfs": -5.8,
        "role_gain_offsets": {"drums": 1.0, "snare": 0.8, "guitar": 1.2, "bass": 0.6, "lead_vocal": 0.7, "keys": -0.6},
    },
    "edm": {
        "label": "EDM",
        "premaster_peak_dbfs": -5.0,
        "role_gain_offsets": {"kick": 1.4, "bass": 1.2, "synth": 1.0, "fx": 0.6, "lead_vocal": -0.2},
    },
    "cinematic": {
        "label": "Cinematic",
        "premaster_peak_dbfs": -8.0,
        "role_gain_offsets": {"keys": 0.8, "synth": 0.7, "fx": 0.8, "drums": -0.7, "lead_vocal": -0.3},
    },
}


def list_audio_genres() -> tuple[str, ...]:
    return tuple(AUDIO_GENRE_PRESETS)


def render_master(
    project: MixProject,
    output_dir: Path,
    master_name: str = "master.wav",
    *,
    genre: str = "balanced",
) -> RenderResult:
    deps = _load_audio_dependencies()
    np = deps["np"]
    sf = deps["sf"]
    output_dir.mkdir(parents=True, exist_ok=True)

    preset_name, preset = _genre_preset(genre)
    sample_rate = project.stems[0].metrics.sample_rate
    processed_stems = [_render_stem(stem, sample_rate, deps, preset) for stem in project.stems]
    warnings = []
    if deps.get("simple_renderer"):
        warnings.append(
            "Using simple shared-hosting renderer because the full pedalboard/librosa chain is unavailable."
        )
    warnings.extend(_attenuate_correlated_ambiguous_stems(project.stems, processed_stems, np))
    mix = _sum_stems(processed_stems, np)
    premaster = _normalize_peak(mix, preset["premaster_peak_dbfs"], np)
    premaster_loudness = analyze_loudness(premaster, sample_rate, np)
    master = _master_bus(premaster, sample_rate, project.mastering_target, deps, preset)
    master_loudness = analyze_loudness(master, sample_rate, np)

    rough_mix_path = output_dir / "rough_mix.wav"
    sf.write(rough_mix_path, premaster, sample_rate, subtype="PCM_24")

    master_path = output_dir / master_name
    sf.write(master_path, master, sample_rate, subtype="PCM_24")

    preview_path = _write_mp3_preview(master_path, warnings)
    if master_loudness.method.startswith("rms-fallback"):
        warnings.append("pyloudnorm is not installed; LUFS used RMS fallback estimation.")
    desired_lufs = target_lufs(project.mastering_target)
    if abs(master_loudness.integrated_lufs - desired_lufs) > 1.0:
        warnings.append("Selected loudness target could not be reached safely without exceeding the true-peak ceiling.")
    from .quality import assess_render_quality

    quality_report = assess_render_quality(project, master_loudness, project.mastering_target).to_dict()
    warnings.extend(item for item in quality_report["warnings"] if item not in warnings)
    return RenderResult(
        master_path=master_path,
        rough_mix_path=rough_mix_path,
        preview_path=preview_path,
        warnings=warnings,
        genre=preset_name,
        premaster_loudness=premaster_loudness,
        master_loudness=master_loudness,
        quality_report=quality_report,
    )


def _load_audio_dependencies() -> dict[str, Any]:
    os.environ.setdefault(
        "NUMBA_CACHE_DIR",
        str(Path(tempfile.gettempdir()) / "imixing_numba_cache"),
    )
    try:
        import numpy as np
        import soundfile as sf
    except ImportError as error:
        raise RuntimeError(
            "Audio rendering requires numpy and soundfile from pyproject.toml. Run `pip install -e .`."
        ) from error

    try:
        import librosa
        from pedalboard import (
            Compressor,
            Gain,
            HighpassFilter,
            HighShelfFilter,
            Limiter,
            LowpassFilter,
            LowShelfFilter,
            PeakFilter,
            Pedalboard,
            Reverb,
        )
    except ImportError as error:
        return {
            "librosa": None,
            "np": np,
            "sf": sf,
            "simple_renderer": True,
            "simple_renderer_reason": repr(error),
        }

    return {
        "librosa": librosa,
        "np": np,
        "sf": sf,
        "simple_renderer": False,
        "Compressor": Compressor,
        "Gain": Gain,
        "HighpassFilter": HighpassFilter,
        "HighShelfFilter": HighShelfFilter,
        "Limiter": Limiter,
        "LowpassFilter": LowpassFilter,
        "LowShelfFilter": LowShelfFilter,
        "PeakFilter": PeakFilter,
        "Pedalboard": Pedalboard,
        "Reverb": Reverb,
    }


def _genre_preset(genre: str) -> tuple[str, dict[str, Any]]:
    key = (genre or "balanced").strip().lower()
    if key not in AUDIO_GENRE_PRESETS:
        key = "balanced"
    return key, AUDIO_GENRE_PRESETS[key]


def _settings_for_role(role: str, preset: dict[str, Any]) -> dict[str, Any]:
    settings = dict(ROLE_RENDER_SETTINGS.get(role, ROLE_RENDER_SETTINGS["other"]))
    offset = preset["role_gain_offsets"].get(role, 0.0)
    settings["gain_db"] += offset
    return settings


def _render_stem(stem: StemPlan, target_sample_rate: int, deps: dict[str, Any], preset: dict[str, Any]):
    librosa = deps["librosa"]
    np = deps["np"]
    sf = deps["sf"]
    audio, source_sample_rate = sf.read(stem.path, dtype="float32", always_2d=True)
    audio = _to_stereo(audio, np)

    if source_sample_rate != target_sample_rate:
        if librosa is not None:
            left = librosa.resample(audio[:, 0], orig_sr=source_sample_rate, target_sr=target_sample_rate)
            right = librosa.resample(audio[:, 1], orig_sr=source_sample_rate, target_sr=target_sample_rate)
            audio = np.column_stack([left, right]).astype(np.float32)
        else:
            audio = _resample_linear(audio, source_sample_rate, target_sample_rate, np)

    settings = _settings_for_role(stem.role, preset)
    audio = _remove_dc(audio, np)
    audio = _apply_adaptive_gain(audio, settings, np)
    audio = _apply_track_board(audio, target_sample_rate, settings, deps)
    audio = _apply_pan(audio, settings.get("pan", 0.0), np)
    audio = _stabilize_stem_peak(audio, settings.get("peak_ceiling_dbfs", -1.5), np)
    return audio.astype(np.float32)


def _apply_track_board(audio, sample_rate: int, settings: dict[str, Any], deps: dict[str, Any]):
    if deps.get("simple_renderer"):
        return _apply_simple_track_processing(audio, sample_rate, settings, deps["np"])

    board = deps["Pedalboard"]()
    if highpass_hz := settings.get("highpass_hz"):
        board.append(deps["HighpassFilter"](cutoff_frequency_hz=highpass_hz))
    for filter_type, frequency, gain_db, q in settings.get("eq", []):
        if filter_type == "low_shelf":
            board.append(deps["LowShelfFilter"](cutoff_frequency_hz=frequency, gain_db=gain_db, q=q))
        elif filter_type == "high_shelf":
            board.append(deps["HighShelfFilter"](cutoff_frequency_hz=frequency, gain_db=gain_db, q=q))
        elif filter_type == "peak":
            board.append(deps["PeakFilter"](cutoff_frequency_hz=frequency, gain_db=gain_db, q=q))
    if lowpass_hz := settings.get("lowpass_hz"):
        board.append(deps["LowpassFilter"](cutoff_frequency_hz=lowpass_hz))
    if compressor := settings.get("compressor"):
        threshold_db, ratio = compressor
        board.append(
            deps["Compressor"](
                threshold_db=threshold_db,
                ratio=ratio,
                attack_ms=12.0,
                release_ms=90.0,
            )
        )
    if reverb := settings.get("reverb"):
        board.append(deps["Reverb"](room_size=0.25, damping=0.55, wet_level=reverb, dry_level=1.0))
    return board(audio, sample_rate)


def _master_bus(audio, sample_rate: int, target: str, deps: dict[str, Any], preset: dict[str, Any]):
    np = deps["np"]
    ceiling = target_true_peak_dbtp(target)
    if deps.get("simple_renderer"):
        return _simple_master_bus(audio, sample_rate, target, ceiling, np)

    compression_board = deps["Pedalboard"](
        [
            deps["Compressor"](threshold_db=-18.0, ratio=1.6, attack_ms=25.0, release_ms=160.0),
        ]
    )
    compressed = compression_board(audio, sample_rate)
    metrics = analyze_loudness(compressed, sample_rate, np)
    target_gain_db = max(-12.0, min(target_lufs(target) - metrics.integrated_lufs, 9.0))
    gained = (compressed * (10.0 ** (target_gain_db / 20.0))).astype(np.float32)
    limited = deps["Pedalboard"]([deps["Limiter"](threshold_db=ceiling, release_ms=80.0)])(gained, sample_rate)
    return _constrain_true_peak(limited, sample_rate, ceiling, np).astype(np.float32)


def _apply_simple_track_processing(audio, sample_rate: int, settings: dict[str, Any], np):
    processed = audio
    if highpass_hz := settings.get("highpass_hz"):
        processed = _simple_highpass(processed, sample_rate, float(highpass_hz), np)
    if lowpass_hz := settings.get("lowpass_hz"):
        processed = _simple_lowpass(processed, sample_rate, float(lowpass_hz), np)
    if settings.get("compressor"):
        processed = _simple_soft_compress(processed, np)
    if reverb := settings.get("reverb"):
        processed = _simple_room(processed, float(reverb), np)
    return processed.astype(np.float32)


def _simple_master_bus(audio, sample_rate: int, target: str, ceiling: float, np):
    compressed = _simple_soft_compress(audio, np, drive=1.15)
    metrics = analyze_loudness(compressed, sample_rate, np)
    target_gain_db = max(-12.0, min(target_lufs(target) - metrics.integrated_lufs, 9.0))
    gained = (compressed * (10.0 ** (target_gain_db / 20.0))).astype(np.float32)
    limited = np.tanh(gained * 1.05).astype(np.float32)
    return _constrain_true_peak(limited, sample_rate, ceiling, np).astype(np.float32)


def _simple_soft_compress(audio, np, drive: float = 1.0):
    return np.tanh(audio * drive).astype(np.float32)


def _simple_room(audio, wet: float, np):
    delay = max(1, min(audio.shape[0] - 1, int(0.045 * 44100)))
    room = audio.copy()
    room[delay:, :] += audio[:-delay, :] * min(0.18, wet * 1.4)
    return _stabilize_stem_peak(room, -1.2, np)


def _simple_highpass(audio, sample_rate: int, cutoff_hz: float, np):
    if cutoff_hz <= 0 or audio.shape[0] < 2:
        return audio.astype(np.float32)
    rc = 1.0 / (2.0 * math.pi * cutoff_hz)
    dt = 1.0 / float(sample_rate)
    alpha = rc / (rc + dt)
    output = np.zeros_like(audio, dtype=np.float32)
    output[0, :] = audio[0, :]
    for index in range(1, audio.shape[0]):
        output[index, :] = alpha * (output[index - 1, :] + audio[index, :] - audio[index - 1, :])
    return output.astype(np.float32)


def _simple_lowpass(audio, sample_rate: int, cutoff_hz: float, np):
    if cutoff_hz <= 0 or audio.shape[0] < 2:
        return audio.astype(np.float32)
    rc = 1.0 / (2.0 * math.pi * cutoff_hz)
    dt = 1.0 / float(sample_rate)
    alpha = dt / (rc + dt)
    output = np.zeros_like(audio, dtype=np.float32)
    output[0, :] = audio[0, :]
    for index in range(1, audio.shape[0]):
        output[index, :] = output[index - 1, :] + alpha * (audio[index, :] - output[index - 1, :])
    return output.astype(np.float32)


def _resample_linear(audio, source_sample_rate: int, target_sample_rate: int, np):
    if source_sample_rate == target_sample_rate:
        return audio.astype(np.float32)
    duration = audio.shape[0] / float(source_sample_rate)
    target_length = max(1, int(round(duration * target_sample_rate)))
    source_positions = np.linspace(0.0, max(0, audio.shape[0] - 1), num=audio.shape[0])
    target_positions = np.linspace(0.0, max(0, audio.shape[0] - 1), num=target_length)
    left = np.interp(target_positions, source_positions, audio[:, 0])
    right = np.interp(target_positions, source_positions, audio[:, 1])
    return np.column_stack([left, right]).astype(np.float32)


def _sum_stems(stems: list[Any], np):
    max_length = max(stem.shape[0] for stem in stems)
    mix = np.zeros((max_length, 2), dtype=np.float32)
    for stem in stems:
        mix[: stem.shape[0], :] += stem
    return mix


def _to_stereo(audio, np):
    if audio.ndim == 1:
        return np.column_stack([audio, audio]).astype(np.float32)
    if audio.shape[1] == 1:
        return np.column_stack([audio[:, 0], audio[:, 0]]).astype(np.float32)
    if audio.shape[1] >= 2 and audio.shape[0] > audio.shape[1]:
        return audio[:, :2].astype(np.float32)
    if audio.shape[0] == 1:
        return np.column_stack([audio[0], audio[0]]).astype(np.float32)
    if audio.shape[0] == 2:
        return audio.T.astype(np.float32)
    return audio[:2].T.astype(np.float32)


def _remove_dc(audio, np):
    return (audio - np.mean(audio, axis=0, keepdims=True)).astype(np.float32)


def _apply_adaptive_gain(audio, settings: dict[str, Any], np):
    target = settings.get("target_rms_dbfs")
    static_gain = settings.get("gain_db", 0.0)
    if target is None:
        gain_db = static_gain
    else:
        current = _rms_dbfs(audio, np)
        gain_db = target - current + static_gain
        gain_db = max(settings.get("min_gain_db", -18.0), min(gain_db, settings.get("max_gain_db", 6.0)))
    return (audio * (10.0 ** (gain_db / 20.0))).astype(np.float32)


def _rms_dbfs(audio, np) -> float:
    rms = float(np.sqrt(np.mean(np.square(audio))) + 1e-12)
    return 20.0 * math.log10(rms)


def _stabilize_stem_peak(audio, ceiling_dbfs: float, np):
    peak = _peak_dbfs(audio, np)
    if peak <= ceiling_dbfs:
        return audio.astype(np.float32)
    gain = 10.0 ** ((ceiling_dbfs - peak) / 20.0)
    return (audio * gain).astype(np.float32)


def _apply_pan(audio, pan: float, np):
    pan = max(-1.0, min(1.0, pan))
    angle = (pan + 1.0) * math.pi / 4.0
    left_gain = math.cos(angle) * math.sqrt(2.0)
    right_gain = math.sin(angle) * math.sqrt(2.0)
    panned = audio.copy()
    panned[:, 0] *= left_gain
    panned[:, 1] *= right_gain
    return panned.astype(np.float32)


def _normalize_peak(audio, peak_dbfs: float, np):
    peak = float(np.max(np.abs(audio)))
    if peak <= 0:
        return audio.astype(np.float32)
    current_peak_db = 20.0 * math.log10(peak)
    gain = 10.0 ** ((peak_dbfs - current_peak_db) / 20.0)
    return (audio * gain).astype(np.float32)


def _attenuate_correlated_ambiguous_stems(stems: list[StemPlan], processed_stems: list[Any], np) -> list[str]:
    warnings = []
    for index, stem in enumerate(stems):
        if stem.role != "other":
            continue

        best_name = ""
        best_correlation = 0.0
        for other_index, other_stem in enumerate(stems):
            if other_index == index or other_stem.role == "other":
                continue
            correlation = _abs_correlation(processed_stems[index], processed_stems[other_index], np)
            if correlation > best_correlation:
                best_name = other_stem.filename
                best_correlation = correlation

        if best_correlation >= 0.6 or _looks_like_placeholder(stem.filename):
            attenuation_db = -10.0
            processed_stems[index] = (processed_stems[index] * (10.0 ** (attenuation_db / 20.0))).astype(np.float32)
            if best_name:
                warnings.append(
                    f"{stem.filename} is highly correlated with {best_name}; rendered {abs(attenuation_db):.0f} dB lower to avoid doubling."
                )
            else:
                warnings.append(f"{stem.filename} looks like a placeholder stem; rendered {abs(attenuation_db):.0f} dB lower.")
    return warnings


def _looks_like_placeholder(filename: str) -> bool:
    normalized = Path(filename).stem.strip().lower().replace("-", " ").replace("_", " ")
    return normalized in {"test", "demo", "mix", "master", "rough", "bounce", "export"}


def _abs_correlation(first, second, np) -> float:
    length = min(first.shape[0], second.shape[0])
    if length < 2:
        return 0.0
    step = max(1, length // 250_000)
    first_mono = first[:length:step, :].mean(axis=1)
    second_mono = second[:length:step, :].mean(axis=1)
    first_mono = first_mono - float(np.mean(first_mono))
    second_mono = second_mono - float(np.mean(second_mono))
    denominator = float(np.sqrt(np.mean(first_mono * first_mono)) * np.sqrt(np.mean(second_mono * second_mono)))
    if denominator <= 1e-9:
        return 0.0
    return abs(float(np.mean(first_mono * second_mono) / denominator))


def _constrain_true_peak(audio, sample_rate: int, ceiling_dbtp: float, np):
    metrics = analyze_loudness(audio, sample_rate, np)
    if metrics.true_peak_dbtp <= ceiling_dbtp:
        return audio.astype(np.float32)
    gain = 10.0 ** ((ceiling_dbtp - metrics.true_peak_dbtp) / 20.0)
    return (audio * gain).astype(np.float32)


def _peak_dbfs(audio, np) -> float:
    peak = float(np.max(np.abs(audio)))
    if peak <= 0:
        return -120.0
    return 20.0 * math.log10(peak)


def _write_mp3_preview(master_path: Path, warnings: list[str]) -> Path | None:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        warnings.append("FFmpeg was not found; skipped MP3 preview export.")
        return None

    preview_path = master_path.with_suffix(".mp3")
    command = [
        ffmpeg,
        "-y",
        "-i",
        str(master_path),
        "-codec:a",
        "libmp3lame",
        "-b:a",
        "320k",
        str(preview_path),
    ]
    completed = subprocess.run(command, check=False, capture_output=True, text=True)
    if completed.returncode != 0:
        warnings.append("FFmpeg MP3 preview export failed.")
        return None
    return preview_path
