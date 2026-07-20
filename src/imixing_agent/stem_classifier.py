from __future__ import annotations

from pathlib import Path

from .models import AudioMetrics


ROLE_KEYWORDS: dict[str, tuple[str, ...]] = {
    "kick": ("kick", "bd", "бочка"),
    "snare": ("snare", "sd", "clap", "снейр", "малый"),
    "drums": ("drum", "drums", "perc", "percussion", "hat", "cymbal", "барабан"),
    "bass": ("bass", "sub", "808", "бас"),
    "backing_vocals": ("backing", "bvox", "choir", "harmony", "бек"),
    "lead_vocal": ("lead vocal", "lead_vocal", "vocal", "vox", "voice", "вокал"),
    "guitar": ("guitar", "gtr", "гитара"),
    "keys": ("piano", "keys", "keyboard", "rhodes", "organ", "melody", "melodic", "пиано", "клав", "мелод"),
    "synth": ("synth", "pad", "lead", "arp", "синт"),
    "fx": ("fx", "sfx", "riser", "impact", "noise", "эффект"),
}


def classify_stem(path: Path, metrics: AudioMetrics | None = None) -> str:
    normalized = path.stem.lower().replace("-", " ").replace("_", " ")

    for role, keywords in ROLE_KEYWORDS.items():
        if any(keyword in normalized for keyword in keywords):
            return role

    inferred = _classify_signal(metrics)
    if inferred:
        return inferred
    return "other"


def _classify_signal(metrics: AudioMetrics | None) -> str | None:
    """Conservative signal-based fallback for filenames that carry no production context."""
    if not metrics or metrics.spectral_centroid_hz is None:
        return None

    centroid = metrics.spectral_centroid_hz
    low = metrics.low_band_ratio or 0.0
    mid = metrics.mid_band_ratio or 0.0
    high = metrics.high_band_ratio or 0.0
    transient = metrics.peak_dbfs - metrics.rms_dbfs

    if low >= 0.58 and centroid <= 240:
        return "kick" if transient >= 13.0 else "bass"
    if low >= 0.38 and centroid <= 420:
        return "bass"
    if high >= 0.7 and centroid >= 5500:
        return "fx"
    if 600 <= centroid <= 3000 and mid >= 0.55 and 4.0 <= transient <= 16.0:
        return "lead_vocal"
    return None
