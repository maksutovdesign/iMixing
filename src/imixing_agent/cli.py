from __future__ import annotations

import argparse
from pathlib import Path

from .mix_strategy import build_project
from .reporting import write_reports
from .rendering import render_master


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Analyze separated music stems and generate a mix/mastering plan."
    )
    parser.add_argument("input_dir", type=Path, help="Folder containing WAV stems.")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("out"),
        help="Folder for analysis.json and mix_plan.md.",
    )
    parser.add_argument(
        "--target",
        default="streaming:-14LUFS:-1dBTP",
        help="Mastering target label.",
    )
    parser.add_argument(
        "--no-render",
        action="store_true",
        help="Only write analysis reports; skip audio rendering.",
    )
    parser.add_argument(
        "--master-name",
        default="master.wav",
        help="Filename for the rendered WAV master.",
    )
    args = parser.parse_args()

    try:
        project = build_project(args.input_dir, args.target)
    except (FileNotFoundError, NotADirectoryError, ValueError) as error:
        parser.exit(2, f"Analysis failed: {error}\n")
    write_reports(project, args.output)

    print(f"Analyzed {len(project.stems)} stem(s).")
    print(f"Wrote {args.output / 'analysis.json'}")
    print(f"Wrote {args.output / 'mix_plan.md'}")

    if not args.no_render:
        try:
            result = render_master(project, args.output, args.master_name)
        except RuntimeError as error:
            parser.exit(2, f"Render failed: {error}\n")
        print(f"Wrote {result.master_path}")
        if result.preview_path:
            print(f"Wrote {result.preview_path}")
        for warning in result.warnings:
            print(f"Warning: {warning}")


if __name__ == "__main__":
    main()
