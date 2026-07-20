from __future__ import annotations

import base64
import random
from dataclasses import asdict, dataclass
from typing import Iterable

from .midi_fixer import Note, PITCH_CLASS_NAMES, render_midi_bytes


DIVISION = 480
MAX_DURATION_SECONDS = 600
MIN_BPM = 40
MAX_BPM = 240
GENERATOR_PARTS = ("bass", "melody", "drums")
GENERATOR_STYLES = ("pop", "rap", "trap", "house", "techno", "edm", "rock", "cinematic", "jazz")
SCALES = {
    "major": (0, 2, 4, 5, 7, 9, 11),
    "minor": (0, 2, 3, 5, 7, 8, 10),
}
ROOT_NAMES = {name.upper().replace("B", "B"): index for index, name in enumerate(PITCH_CLASS_NAMES)}
ROOT_ALIASES = {"DB": 1, "EB": 3, "GB": 6, "AB": 8, "BB": 10, "CB": 11, "FB": 4, "E#": 5, "B#": 0}

STYLE_PROGRESSIONS = {
    "pop": (0, 5, 3, 4),
    "rap": (0, 5, 3, 4),
    "trap": (0, 5, 2, 6),
    "house": (0, 4, 5, 3),
    "techno": (0, 0, 5, 3),
    "edm": (0, 4, 5, 3),
    "rock": (0, 3, 4, 0),
    "cinematic": (0, 5, 3, 6),
    "jazz": (1, 4, 0, 5),
}


@dataclass(frozen=True)
class MidiGenerationOptions:
    bpm: int = 120
    duration_seconds: int = 60
    key: str = "C"
    scale: str = "minor"
    style: str = "pop"
    swing: float = 0.0
    humanize: float = 0.15
    density: float = 0.6
    parts: tuple[str, ...] = GENERATOR_PARTS
    seed: int | None = None
    motif: str = ""


@dataclass(frozen=True)
class MidiGenerationResult:
    midi_bytes: bytes
    filename: str
    stats: dict[str, object]

    def to_api_dict(self) -> dict[str, object]:
        return {
            "filename": self.filename,
            "midi_base64": base64.b64encode(self.midi_bytes).decode("ascii"),
            "stats": self.stats,
        }


def list_generator_styles() -> tuple[str, ...]:
    return GENERATOR_STYLES


def generate_midi(options: MidiGenerationOptions) -> MidiGenerationResult:
    _validate(options)
    root = _parse_root(options.key)
    rng = random.Random(options.seed if options.seed is not None else _stable_seed(options))
    bar_ticks = DIVISION * 4
    bar_count = max(1, round(options.duration_seconds * options.bpm / 60 / 4))
    progression = STYLE_PROGRESSIONS[options.style]
    scale = SCALES[options.scale]
    motif = _parse_motif(options.motif)
    notes: list[Note] = []

    for bar in range(bar_count):
        bar_start = bar * bar_ticks
        degree = progression[bar % len(progression)]
        chord_root = root + scale[degree % len(scale)]
        if "bass" in options.parts:
            notes.extend(_bass_bar(bar_start, chord_root, options, rng))
        if "melody" in options.parts:
            notes.extend(_melody_bar(bar_start, chord_root, root, scale, motif, bar, options, rng))
        if "drums" in options.parts:
            notes.extend(_drum_bar(bar_start, bar, bar_count, options, rng))

    notes.sort(key=lambda note: (note.start, note.channel, note.pitch, note.end))
    tempo = round(60_000_000 / options.bpm)
    meta_events = [
        (0, b"\x51\x03" + tempo.to_bytes(3, "big")),
        (0, b"\x58\x04\x04\x02\x18\x08"),
    ]
    title = f"iMixing {PITCH_CLASS_NAMES[root]} {options.scale} {options.style} generator"
    midi_bytes = render_midi_bytes(
        DIVISION,
        meta_events,
        notes,
        title,
        output_format=1,
        include_track_titles=True,
    )
    counts = {part: sum(1 for note in notes if _part_for_channel(note.channel) == part) for part in GENERATOR_PARTS}
    return MidiGenerationResult(
        midi_bytes=midi_bytes,
        filename=f"imixing_{options.style}_{options.key.lower().replace('#', 'sharp')}_{options.duration_seconds}s.mid",
        stats={
            "bpm": options.bpm,
            "duration_seconds": round(bar_count * 4 * 60 / options.bpm, 1),
            "bars": bar_count,
            "key": f"{PITCH_CLASS_NAMES[root]} {options.scale}",
            "style": options.style,
            "swing": options.swing,
            "humanize": options.humanize,
            "density": options.density,
            "parts": list(options.parts),
            "note_counts": counts,
            "seed": options.seed if options.seed is not None else _stable_seed(options),
        },
    )


def _bass_bar(start: int, root: int, options: MidiGenerationOptions, rng: random.Random) -> list[Note]:
    pattern = {
        "trap": (0, 3, 6, 7), "rap": (0, 3, 6, 7), "house": (0, 2, 4, 6), "techno": (0, 2, 4, 6),
        "edm": (0, 2, 4, 6), "rock": (0, 4, 6), "jazz": (0, 2, 4, 6),
    }.get(options.style, (0, 2, 4, 6))
    step = DIVISION // 2
    notes = []
    for index, position in enumerate(pattern):
        if index and rng.random() > options.density:
            continue
        pitch = 36 + (root % 12)
        if options.style == "jazz" and index % 2:
            pitch += 7
        elif options.style in {"trap", "rap"} and index == len(pattern) - 1:
            pitch += 12
        tick = _groove_tick(start + position * step, step, options, rng)
        notes.append(Note(tick, tick + int(step * 0.8), pitch, rng.randint(72, 98), 1))
    return notes


def _melody_bar(
    start: int, chord_root: int, root: int, scale: tuple[int, ...], motif: list[int], bar: int,
    options: MidiGenerationOptions, rng: random.Random,
) -> list[Note]:
    step = DIVISION // 2
    positions = (0, 2, 4, 6) if options.density < 0.72 else tuple(range(8))
    notes = []
    for index, position in enumerate(positions):
        if index and rng.random() > options.density:
            continue
        if motif:
            pitch = motif[(bar * len(positions) + index) % len(motif)]
        else:
            chord_tone = (0, 2, 4)[(index + bar) % 3]
            pitch = 72 + (chord_root + scale[chord_tone % len(scale)] - root) % 12
            while pitch > 88:
                pitch -= 12
        tick = _groove_tick(start + position * step, step, options, rng)
        duration = int(step * (0.65 if index % 2 else 0.9))
        notes.append(Note(tick, tick + duration, pitch, rng.randint(58, 92), 0))
    return notes


def _drum_bar(start: int, bar: int, total_bars: int, options: MidiGenerationOptions, rng: random.Random) -> list[Note]:
    sixteenth = DIVISION // 4
    kick_pattern = (0, 6, 8, 12) if options.style in {"trap", "rap"} else (0, 8) if options.style in {"house", "techno", "edm"} else (0, 7, 8, 12)
    snare_pattern = (4, 12) if options.style in {"trap", "rap"} else (4, 12)
    notes = []
    for step in range(16):
        tick = _groove_tick(start + step * sixteenth, sixteenth, options, rng)
        if step in kick_pattern:
            notes.append(Note(tick, tick + 72, 36, rng.randint(92, 116), 9))
        if step in snare_pattern:
            notes.append(Note(tick, tick + 72, 38, rng.randint(86, 108), 9))
        hat_every = 1 if options.style in {"house", "techno", "edm"} and options.density > 0.7 else 2
        if step % hat_every == 0:
            velocity = 74 if step % 4 == 0 else rng.randint(42, 66)
            notes.append(Note(tick, tick + 42, 42, velocity, 9))
        if step in (7, 15) and rng.random() < options.density * 0.35:
            notes.append(Note(tick, tick + 36, 42, rng.randint(24, 42), 9))
    if bar == total_bars - 1 or (bar + 1) % 8 == 0:
        for step in (12, 13, 14, 15):
            tick = _groove_tick(start + step * sixteenth, sixteenth, options, rng)
            notes.append(Note(tick, tick + 35, 46, 62 + step * 3, 9))
    return notes


def _groove_tick(tick: int, step: int, options: MidiGenerationOptions, rng: random.Random) -> int:
    swung = int(round(options.swing * step * 0.8)) if (tick // step) % 2 else 0
    jitter = int(round(rng.uniform(-1, 1) * options.humanize * min(18, step * 0.1)))
    return max(0, tick + swung + jitter)


def _parse_root(value: str) -> int:
    normalized = (value or "C").strip().upper().replace("♯", "#").replace("♭", "B")
    if normalized in ROOT_ALIASES:
        return ROOT_ALIASES[normalized]
    for index, name in enumerate(PITCH_CLASS_NAMES):
        if normalized == name.upper():
            return index
    raise ValueError("Unsupported key. Use C, C#, D, Eb, E, F, F#, G, Ab, A, Bb, or B.")


def _parse_motif(value: str) -> list[int]:
    values = []
    for token in (value or "").replace(" ", ",").split(","):
        token = token.strip()
        if not token:
            continue
        try:
            values.append(max(36, min(96, int(token))))
        except ValueError:
            continue
    return values[:32]


def _part_for_channel(channel: int) -> str:
    return "drums" if channel == 9 else "bass" if channel == 1 else "melody"


def _stable_seed(options: MidiGenerationOptions) -> int:
    return abs(hash((options.bpm, options.duration_seconds, options.key, options.scale, options.style, options.motif))) % (2**31)


def _validate(options: MidiGenerationOptions) -> None:
    if not MIN_BPM <= options.bpm <= MAX_BPM:
        raise ValueError(f"BPM must be between {MIN_BPM} and {MAX_BPM}.")
    if not 4 <= options.duration_seconds <= MAX_DURATION_SECONDS:
        raise ValueError(f"Duration must be between 4 and {MAX_DURATION_SECONDS} seconds.")
    if options.scale not in SCALES:
        raise ValueError("Scale must be major or minor.")
    if options.style not in GENERATOR_STYLES:
        raise ValueError("Unsupported generator style.")
    if not 0.0 <= options.swing <= 0.5 or not 0.0 <= options.humanize <= 1.0 or not 0.1 <= options.density <= 1.0:
        raise ValueError("Swing, humanize, or density is outside its supported range.")
    if not options.parts or any(part not in GENERATOR_PARTS for part in options.parts):
        raise ValueError("Choose at least one supported generator part.")
