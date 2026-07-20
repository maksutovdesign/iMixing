from __future__ import annotations

from pathlib import Path

from .audio_analysis import analyze_wav
from .models import MixProject, StemPlan
from .stem_classifier import classify_stem


ROLE_CHAINS: dict[str, list[str]] = {
    "kick": [
        "Trim gain to keep peak around -8 to -6 dBFS before bus processing.",
        "High-pass only below useless sub-rumble if needed.",
        "Shape low fundamental and click area with corrective EQ.",
        "Use controlled compression for punch, not constant flattening.",
        "Keep mono and route to drums bus plus low-end check.",
    ],
    "snare": [
        "Trim gain to sit above drum ambience without clipping.",
        "Remove low mud, shape body and crack with EQ.",
        "Use transient shaping for attack if the arrangement needs impact.",
        "Add short room or plate reverb send.",
        "Route to drums bus.",
    ],
    "drums": [
        "Balance internal drum level before bus compression.",
        "Clean low rumble and harsh cymbal bands.",
        "Use parallel compression for density.",
        "Add subtle saturation for cohesion.",
        "Route to drums bus with gentle glue compression.",
    ],
    "bass": [
        "Trim gain so low end has headroom against the kick.",
        "High-pass below musical sub range.",
        "Use compression to stabilize note-to-note dynamics.",
        "Add harmonic saturation for small-speaker translation.",
        "Keep sub information mono and route to music bus.",
    ],
    "lead_vocal": [
        "Trim gain for consistent level before compression.",
        "High-pass unnecessary lows and remove resonances.",
        "Use serial compression for stable presence.",
        "Apply de-essing before brightening.",
        "Add short ambience and tempo-aware delay sends.",
    ],
    "backing_vocals": [
        "Group and trim below the lead vocal.",
        "High-pass to avoid low-mid buildup.",
        "Compress gently for blend.",
        "De-ess as a group.",
        "Pan or widen carefully around the lead vocal.",
    ],
    "guitar": [
        "Trim gain to support the vocal without masking it.",
        "High-pass below the useful range.",
        "Cut harsh or boxy resonances.",
        "Use light compression only if performance dynamics distract.",
        "Pan according to arrangement density.",
    ],
    "keys": [
        "Trim gain to leave room for vocal and drums.",
        "Filter low frequencies that conflict with bass.",
        "Shape mids based on harmonic role.",
        "Use stereo width only after mono compatibility check.",
        "Route to music bus.",
    ],
    "synth": [
        "Trim gain to avoid masking drums and vocal.",
        "Filter unnecessary lows and harsh highs.",
        "Use sidechain-style movement if it fights the kick.",
        "Control width in the low end.",
        "Route to music bus.",
    ],
    "fx": [
        "Trim gain so effects support transitions without clipping.",
        "Filter low rumble.",
        "Automate width and level around arrangement moments.",
        "Use reverb or delay sends only where needed.",
        "Route to effects bus.",
    ],
    "other": [
        "Trim gain conservatively and inspect in context.",
        "Remove low rumble.",
        "Use corrective EQ for resonances.",
        "Apply compression only if dynamics distract from the song.",
        "Route to music bus.",
    ],
}


MIX_BUS_CHAIN = [
    "Leave at least 6 dB of true headroom before mastering.",
    "Apply subtle tonal EQ after the rough balance is stable.",
    "Use gentle bus compression for cohesion, aiming for light gain reduction.",
    "Add very subtle saturation only if the mix needs density.",
    "Check mono compatibility before printing the premaster.",
]


MASTERING_CHAIN = [
    "Broad tonal EQ for translation across systems.",
    "Dynamic control only where the mix has unstable frequency ranges.",
    "Stereo image check with low frequencies kept centered.",
    "Final limiter with true-peak ceiling around -1 dBTP.",
    "Export high-resolution WAV plus streaming-ready derivative if needed.",
]


def build_project(input_dir: Path, mastering_target: str) -> MixProject:
    audio_paths = sorted(path for path in input_dir.iterdir() if path.suffix.lower() == ".wav")
    if not audio_paths:
        raise FileNotFoundError(f"No WAV stems found in {input_dir}")

    stems = [_build_stem_plan(path) for path in audio_paths]
    notes = _build_project_notes(stems)

    return MixProject(
        stems=stems,
        mastering_target=mastering_target,
        mix_bus_chain=MIX_BUS_CHAIN,
        mastering_chain=MASTERING_CHAIN,
        notes=notes,
    )


def _build_stem_plan(path: Path) -> StemPlan:
    metrics = analyze_wav(path)
    role = classify_stem(path, metrics)
    warnings = _warnings_for(metrics)

    return StemPlan(
        path=str(path),
        role=role,
        metrics=metrics,
        gain_note=_gain_note(metrics),
        processing_chain=ROLE_CHAINS[role],
        routing=_routing_for(role),
        warnings=warnings,
    )


def _gain_note(metrics) -> str:
    if metrics.peak_dbfs > -1.0:
        return "Reduce clip gain before processing; the stem is too close to full scale."
    if metrics.peak_dbfs < -18.0:
        return "Increase clip gain before processing; the stem is very quiet."
    return "Clip gain is workable for a first-pass mix."


def _warnings_for(metrics) -> list[str]:
    warnings = []
    if metrics.clipping_samples:
        warnings.append(f"Detected {metrics.clipping_samples} samples near full-scale clipping.")
    if metrics.sample_rate < 44100:
        warnings.append("Sample rate is below common music production standards.")
    if metrics.duration_seconds <= 0:
        warnings.append("Duration could not be measured.")
    return warnings


def _routing_for(role: str) -> list[str]:
    if role in {"kick", "snare", "drums"}:
        return ["Track", "Drums Bus", "Mix Bus", "Master"]
    if role in {"lead_vocal", "backing_vocals"}:
        return ["Track", "Vocal Bus", "Mix Bus", "Master"]
    if role == "fx":
        return ["Track", "Effects Bus", "Mix Bus", "Master"]
    return ["Track", "Music Bus", "Mix Bus", "Master"]


def _build_project_notes(stems: list[StemPlan]) -> list[str]:
    roles = {stem.role for stem in stems}
    notes = ["Start with static balance before inserting heavy processing."]

    if "bass" in roles and ("kick" in roles or "drums" in roles):
        notes.append("Prioritize kick and bass relationship before vocal rides.")
    if "lead_vocal" in roles:
        notes.append("Build the final balance around vocal intelligibility.")
    if len(stems) < 3:
        notes.append("Project has few stems; avoid overprocessing and preserve arrangement space.")

    return notes
