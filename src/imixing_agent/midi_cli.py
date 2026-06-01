from __future__ import annotations

import argparse
from pathlib import Path

from .midi_fixer import (
    MidiFixOptions,
    fix_midi_file,
    list_instrument_family_names,
    list_style_names,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Clean, requantize, and revoice a MIDI file into a more theory-aligned arrangement."
    )
    parser.add_argument("input", type=Path, help="Source MIDI file.")
    parser.add_argument("output", type=Path, help="Where to write the edited MIDI file.")
    parser.add_argument(
        "--style",
        choices=list_style_names(),
        default="balanced",
        help="Musical cleanup profile.",
    )
    parser.add_argument(
        "--instrument-family",
        choices=list_instrument_family_names(),
        default="harmony",
        help="Choose between harmonic cleanup, keyboard voicing, or melodic reduction.",
    )
    parser.add_argument(
        "--output-format",
        type=int,
        choices=(0, 1),
        default=1,
        help="Use format 1 by default for better DAW compatibility.",
    )
    parser.add_argument(
        "--include-track-titles",
        action="store_true",
        help="Include MIDI track title meta-events in the output file.",
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    stats = fix_midi_file(
        args.input,
        args.output,
        options=MidiFixOptions(
            style=args.style,
            instrument_family=args.instrument_family,
            output_format=args.output_format,
            include_track_titles=args.include_track_titles,
        ),
    )

    print(f"Wrote {args.output}")
    print(f"Style: {stats.style}")
    print(f"Instrument family: {stats.instrument_family}")
    print(f"Detected key center: {stats.detected_key_center}")
    print(f"Quantize grid: {stats.quantize_grid}")
    print(
        "Notes: "
        f"{stats.original_note_count} original -> "
        f"{stats.cleaned_note_count} cleaned -> "
        f"{stats.edited_note_count} edited"
    )
    print(
        "Pitch range: "
        f"{stats.original_pitch_range[0]}-{stats.original_pitch_range[1]} original, "
        f"{stats.edited_pitch_range[0]}-{stats.edited_pitch_range[1]} edited"
    )
