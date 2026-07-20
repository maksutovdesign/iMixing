from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class AudioMetrics:
    path: str
    filename: str
    channels: int
    sample_rate: int
    bit_depth: int
    duration_seconds: float
    peak_dbfs: float
    rms_dbfs: float
    estimated_headroom_db: float
    clipping_samples: int
    spectral_centroid_hz: float | None = None
    low_band_ratio: float | None = None
    mid_band_ratio: float | None = None
    high_band_ratio: float | None = None
    stereo_correlation: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class StemPlan:
    path: str
    role: str
    metrics: AudioMetrics
    gain_note: str
    processing_chain: list[str]
    routing: list[str]
    warnings: list[str]

    @property
    def filename(self) -> str:
        return Path(self.path).name

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["metrics"] = self.metrics.to_dict()
        return data


@dataclass(frozen=True)
class MixProject:
    stems: list[StemPlan]
    mastering_target: str
    mix_bus_chain: list[str]
    mastering_chain: list[str]
    notes: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "mastering_target": self.mastering_target,
            "stems": [stem.to_dict() for stem in self.stems],
            "mix_bus_chain": self.mix_bus_chain,
            "mastering_chain": self.mastering_chain,
            "notes": self.notes,
        }
