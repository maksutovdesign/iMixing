from __future__ import annotations

import math
import struct
import wave
from pathlib import Path
from typing import Any

from .models import AudioMetrics

SUPPORTED_SAMPLE_WIDTHS = {1, 2, 3, 4}
CHUNK_FRAMES = 262_144


def analyze_wav(path: Path) -> AudioMetrics:
    try:
        return _analyze_wav_with_soundfile(path)
    except ImportError:
        return _analyze_wav_with_wave(path)


def _analyze_wav_with_soundfile(path: Path) -> AudioMetrics:
    try:
        import numpy as np
        import soundfile as sf
    except ImportError:
        raise

    try:
        with sf.SoundFile(str(path)) as audio_file:
            channels = audio_file.channels
            sample_rate = audio_file.samplerate
            frame_count = len(audio_file)
            bit_depth = _bit_depth_from_subtype(audio_file.subtype)

            peak = 0.0
            square_sum = 0.0
            sample_count = 0
            clipping_samples = 0
            analysis_sample = None

            while True:
                chunk = audio_file.read(CHUNK_FRAMES, dtype="float32", always_2d=True)
                if chunk.size == 0:
                    break
                abs_chunk = np.abs(chunk)
                peak = max(peak, float(np.max(abs_chunk)))
                square_sum += float(np.sum(chunk * chunk))
                sample_count += int(chunk.size)
                clipping_samples += int(np.count_nonzero(abs_chunk >= 0.999))
                if analysis_sample is None:
                    analysis_sample = chunk[: min(len(chunk), 131_072)].copy()
    except Exception as error:  # noqa: BLE001
        raise ValueError(f"Invalid or corrupted WAV file: {path.name}") from error

    if sample_count <= 0:
        raise ValueError("Audio file contains no samples")

    rms = math.sqrt(square_sum / sample_count)
    peak_dbfs = _ratio_to_db(peak)
    rms_dbfs = _ratio_to_db(rms)
    duration = frame_count / sample_rate if sample_rate else 0.0
    spectral = _spectral_metrics(analysis_sample, sample_rate, np)

    return AudioMetrics(
        path=str(path),
        filename=path.name,
        channels=channels,
        sample_rate=sample_rate,
        bit_depth=bit_depth,
        duration_seconds=round(duration, 3),
        peak_dbfs=round(peak_dbfs, 2),
        rms_dbfs=round(rms_dbfs, 2),
        estimated_headroom_db=round(abs(peak_dbfs), 2),
        clipping_samples=clipping_samples,
        **spectral,
    )


def _bit_depth_from_subtype(subtype: Any) -> int:
    normalized = str(subtype).upper()
    for marker, bit_depth in (
        ("PCM_U8", 8),
        ("PCM_S8", 8),
        ("PCM_16", 16),
        ("PCM_24", 24),
        ("PCM_32", 32),
        ("FLOAT", 32),
        ("DOUBLE", 64),
    ):
        if marker in normalized:
            return bit_depth
    return 0


def _spectral_metrics(audio, sample_rate: int, np) -> dict[str, float | None]:
    if audio is None or len(audio) < 64 or not sample_rate:
        return {
            "spectral_centroid_hz": None,
            "low_band_ratio": None,
            "mid_band_ratio": None,
            "high_band_ratio": None,
            "stereo_correlation": None,
        }

    mono = np.mean(audio, axis=1)
    window = np.hanning(len(mono))
    spectrum = np.abs(np.fft.rfft(mono * window)) ** 2
    frequencies = np.fft.rfftfreq(len(mono), 1.0 / sample_rate)
    total = float(np.sum(spectrum))
    if total <= 1e-12:
        return {
            "spectral_centroid_hz": 0.0,
            "low_band_ratio": 0.0,
            "mid_band_ratio": 0.0,
            "high_band_ratio": 0.0,
            "stereo_correlation": None,
        }

    def band_ratio(low: float, high: float) -> float:
        mask = (frequencies >= low) & (frequencies < high)
        return round(float(np.sum(spectrum[mask]) / total), 3)

    correlation = None
    if audio.shape[1] >= 2:
        left = audio[:, 0] - float(np.mean(audio[:, 0]))
        right = audio[:, 1] - float(np.mean(audio[:, 1]))
        denominator = float(np.sqrt(np.mean(left * left)) * np.sqrt(np.mean(right * right)))
        if denominator > 1e-9:
            correlation = round(float(np.mean(left * right) / denominator), 3)

    return {
        "spectral_centroid_hz": round(float(np.sum(frequencies * spectrum) / total), 1),
        "low_band_ratio": band_ratio(20.0, 180.0),
        "mid_band_ratio": band_ratio(180.0, 4000.0),
        "high_band_ratio": band_ratio(4000.0, sample_rate / 2.0),
        "stereo_correlation": correlation,
    }


def _analyze_wav_with_wave(path: Path) -> AudioMetrics:
    try:
        with wave.open(str(path), "rb") as wav_file:
            channels = wav_file.getnchannels()
            sample_rate = wav_file.getframerate()
            sample_width = wav_file.getsampwidth()
            frame_count = wav_file.getnframes()
            frames = wav_file.readframes(frame_count)
    except (wave.Error, EOFError) as error:
        raise ValueError(f"Invalid or corrupted WAV file: {path.name}") from error

    if sample_width not in SUPPORTED_SAMPLE_WIDTHS:
        raise ValueError(f"Unsupported sample width: {sample_width} bytes")

    try:
        samples = _decode_pcm(frames, sample_width)
    except (struct.error, IndexError, ValueError) as error:
        raise ValueError(f"WAV PCM data is truncated or malformed: {path.name}") from error
    if not samples:
        raise ValueError("Audio file contains no samples")

    full_scale = float((1 << (sample_width * 8 - 1)) - 1)
    peak = max(abs(sample) for sample in samples)
    rms = math.sqrt(sum(sample * sample for sample in samples) / len(samples))
    clipping_threshold = full_scale * 0.999
    clipping_samples = sum(1 for sample in samples if abs(sample) >= clipping_threshold)

    peak_dbfs = _ratio_to_db(peak / full_scale)
    rms_dbfs = _ratio_to_db(rms / full_scale)
    duration = frame_count / sample_rate if sample_rate else 0.0

    return AudioMetrics(
        path=str(path),
        filename=path.name,
        channels=channels,
        sample_rate=sample_rate,
        bit_depth=sample_width * 8,
        duration_seconds=round(duration, 3),
        peak_dbfs=round(peak_dbfs, 2),
        rms_dbfs=round(rms_dbfs, 2),
        estimated_headroom_db=round(abs(peak_dbfs), 2),
        clipping_samples=clipping_samples,
    )


def _decode_pcm(frames: bytes, sample_width: int) -> list[int]:
    if sample_width == 1:
        return [sample - 128 for sample in frames]

    if sample_width == 2:
        return list(struct.unpack(f"<{len(frames) // 2}h", frames))

    if sample_width == 3:
        samples = []
        for index in range(0, len(frames), 3):
            chunk = frames[index : index + 3]
            sign_byte = b"\xff" if chunk[2] & 0x80 else b"\x00"
            samples.append(int.from_bytes(chunk + sign_byte, "little", signed=True))
        return samples

    return list(struct.unpack(f"<{len(frames) // 4}i", frames))


def _ratio_to_db(ratio: float) -> float:
    if ratio <= 0:
        return -120.0
    return 20.0 * math.log10(ratio)
