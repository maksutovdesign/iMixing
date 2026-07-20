from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from .loudness import LoudnessMetrics, target_lufs, target_true_peak_dbtp
from .models import MixProject


@dataclass(frozen=True)
class QualityReport:
    status: str
    target_lufs: float
    target_true_peak_dbtp: float
    loudness_delta_lu: float
    true_peak_delta_db: float
    warnings: list[str]
    recommendations: list[str]
    mix_conflicts: list[dict[str, str]]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def assess_render_quality(
    project: MixProject,
    master: LoudnessMetrics,
    target: str,
) -> QualityReport:
    desired_lufs = target_lufs(target)
    desired_peak = target_true_peak_dbtp(target)
    loudness_delta = round(master.integrated_lufs - desired_lufs, 2)
    peak_delta = round(master.true_peak_dbtp - desired_peak, 2)
    warnings: list[str] = []
    recommendations: list[str] = []
    mix_conflicts = detect_mix_conflicts(project)

    clipped_stems = [stem.filename for stem in project.stems if stem.metrics.clipping_samples]
    if clipped_stems:
        warnings.append("Input clipping detected in: " + ", ".join(clipped_stems) + ".")
        recommendations.append("Repair or re-export clipped source stems before a release master.")

    if peak_delta > 0.1:
        warnings.append(f"Master true peak is {master.true_peak_dbtp:.2f} dBTP, above the {desired_peak:.1f} dBTP ceiling.")
    if abs(loudness_delta) > 1.0:
        recommendations.append(
            "Master is outside the chosen loudness target by more than 1 LU; compare the safe and loud versions before release."
        )
    if master.crest_factor_db < 5.0:
        warnings.append("Very low crest factor: limiting may be flattening transients.")
        recommendations.append("Choose a quieter target or reduce mix-bus compression for more punch.")
    if master.loudness_range_lu is not None and master.loudness_range_lu > 14.0:
        recommendations.append("Wide loudness range detected; check quiet sections on mobile and small speakers.")
    if master.method.startswith("rms-fallback"):
        warnings.append("LUFS is estimated because pyloudnorm is not installed in this runtime.")
    for conflict in mix_conflicts:
        recommendations.append(conflict["recommendation"])

    status = "needs_review" if warnings else "ready_for_ab_review"
    return QualityReport(
        status=status,
        target_lufs=desired_lufs,
        target_true_peak_dbtp=desired_peak,
        loudness_delta_lu=loudness_delta,
        true_peak_delta_db=peak_delta,
        warnings=warnings,
        recommendations=recommendations,
        mix_conflicts=mix_conflicts,
    )


def detect_mix_conflicts(project: MixProject) -> list[dict[str, str]]:
    by_role = {stem.role: stem for stem in project.stems}
    conflicts: list[dict[str, str]] = []
    kick = by_role.get("kick") or by_role.get("drums")
    bass = by_role.get("bass")
    if kick and bass:
        kick_low = kick.metrics.low_band_ratio or 0.0
        bass_low = bass.metrics.low_band_ratio or 0.0
        level_gap = abs(kick.metrics.rms_dbfs - bass.metrics.rms_dbfs)
        if kick_low >= 0.25 and bass_low >= 0.25 and level_gap <= 7.0:
            conflicts.append(
                {
                    "type": "low_end_masking",
                    "severity": "medium",
                    "stems": f"{kick.filename} / {bass.filename}",
                    "recommendation": "Potential kick/bass masking: compare the low end in mono and use only gentle, genre-aware ducking.",
                }
            )

    vocal = by_role.get("lead_vocal")
    music = [stem for role, stem in by_role.items() if role in {"keys", "guitar", "synth"}]
    if vocal and music:
        vocal_mid = vocal.metrics.mid_band_ratio or 0.0
        for stem in music:
            if vocal_mid >= 0.35 and (stem.metrics.mid_band_ratio or 0.0) >= 0.35:
                conflicts.append(
                    {
                        "type": "vocal_mid_masking",
                        "severity": "review",
                        "stems": f"{vocal.filename} / {stem.filename}",
                        "recommendation": "Possible vocal midrange masking: audition 1–4 kHz in context before applying dynamic EQ.",
                    }
                )
                break

    for stem in project.stems:
        correlation = stem.metrics.stereo_correlation
        if correlation is not None and correlation < -0.2:
            conflicts.append(
                {
                    "type": "phase_risk",
                    "severity": "high",
                    "stems": stem.filename,
                    "recommendation": f"{stem.filename} has negative stereo correlation; check mono compatibility before release.",
                }
            )
    return conflicts
