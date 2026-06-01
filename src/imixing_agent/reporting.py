from __future__ import annotations

import json
from pathlib import Path

from .models import MixProject


def write_reports(project: MixProject, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "analysis.json").write_text(
        json.dumps(project.to_dict(), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    (output_dir / "mix_plan.md").write_text(render_markdown(project), encoding="utf-8")


def render_markdown(project: MixProject) -> str:
    lines = [
        "# iMixing Mix Plan",
        "",
        f"Mastering target: `{project.mastering_target}`",
        "",
        "## Project Notes",
        "",
    ]

    lines.extend(f"- {note}" for note in project.notes)
    lines.extend(["", "## Stems", ""])

    for stem in project.stems:
        metrics = stem.metrics
        lines.extend(
            [
                f"### {stem.filename}",
                "",
                f"- Role: `{stem.role}`",
                f"- Duration: `{metrics.duration_seconds}s`",
                f"- Format: `{metrics.channels} channel(s), {metrics.sample_rate} Hz, {metrics.bit_depth}-bit`",
                f"- Peak: `{metrics.peak_dbfs} dBFS`",
                f"- RMS: `{metrics.rms_dbfs} dBFS`",
                f"- Gain staging: {stem.gain_note}",
                f"- Routing: {' -> '.join(stem.routing)}",
                "",
                "Processing chain:",
                "",
            ]
        )
        lines.extend(f"- {step}" for step in stem.processing_chain)
        if stem.warnings:
            lines.extend(["", "Warnings:", ""])
            lines.extend(f"- {warning}" for warning in stem.warnings)
        lines.append("")

    lines.extend(["## Mix Bus", ""])
    lines.extend(f"- {step}" for step in project.mix_bus_chain)
    lines.extend(["", "## Mastering", ""])
    lines.extend(f"- {step}" for step in project.mastering_chain)
    lines.append("")

    return "\n".join(lines)
