from __future__ import annotations

import struct
from collections import Counter, defaultdict
from dataclasses import dataclass, replace
from itertools import product
from pathlib import Path


PITCH_CLASS_NAMES = ["C", "C#", "D", "Eb", "E", "F", "F#", "G", "Ab", "A", "Bb", "B"]


@dataclass(frozen=True)
class Note:
    start: int
    end: int
    pitch: int
    velocity: int
    channel: int = 0


@dataclass(frozen=True)
class ParsedMidi:
    division: int
    meta_events: list[tuple[int, bytes]]
    notes: list[Note]
    title: str | None


@dataclass(frozen=True)
class ScaleProfile:
    slug: str
    label: str
    intervals: tuple[int, ...]
    detection_bias: float = 0.0


SCALE_PROFILES: dict[str, ScaleProfile] = {
    "major": ScaleProfile(
        slug="major",
        label="major",
        intervals=(0, 2, 4, 5, 7, 9, 11),
        detection_bias=0.0,
    ),
    "minor": ScaleProfile(
        slug="minor",
        label="minor",
        intervals=(0, 2, 3, 5, 7, 8, 10),
        detection_bias=0.2,
    ),
    "harmonic_minor": ScaleProfile(
        slug="harmonic_minor",
        label="harmonic minor",
        intervals=(0, 2, 3, 5, 7, 8, 11),
        detection_bias=-0.35,
    ),
}


@dataclass(frozen=True)
class TonalCenter:
    root: int
    scale: ScaleProfile
    score: float = 0.0


@dataclass(frozen=True)
class StyleProfile:
    slug: str
    label: str
    description: str
    priority_order: tuple[int, ...]
    duplicate_order: tuple[int, ...]
    grid_candidates: tuple[int, ...]
    narrow_voice_limit: int
    wide_voice_limit: int
    bass_range: tuple[int, int]
    inner_range: tuple[int, int]
    melody_range: tuple[int, int]
    inner_center: int
    inner_spread: int
    min_bass_gap: int
    min_inner_gap: int
    max_inner_gap: int
    low_cluster_cutoff: int
    strong_accent: int
    medium_accent: int
    weak_accent: int
    bass_velocity_bonus: int
    melody_velocity_bonus: int
    extension_duplicate_penalty: int


STYLE_PROFILES: dict[str, StyleProfile] = {
    "balanced": StyleProfile(
        slug="balanced",
        label="Balanced",
        description="General-purpose cleanup with moderate density and stable top/bass voices.",
        priority_order=(0, 1, 2, 3, 4),
        duplicate_order=(0, 4, 1),
        grid_candidates=(12, 24),
        narrow_voice_limit=4,
        wide_voice_limit=5,
        bass_range=(36, 55),
        inner_range=(52, 79),
        melody_range=(64, 96),
        inner_center=67,
        inner_spread=5,
        min_bass_gap=8,
        min_inner_gap=2,
        max_inner_gap=11,
        low_cluster_cutoff=60,
        strong_accent=8,
        medium_accent=4,
        weak_accent=-2,
        bass_velocity_bonus=4,
        melody_velocity_bonus=6,
        extension_duplicate_penalty=24,
    ),
    "piano": StyleProfile(
        slug="piano",
        label="Piano",
        description="Open-handed spacing with clear bass support and a singing upper line.",
        priority_order=(0, 1, 4, 2, 3),
        duplicate_order=(0, 4, 1),
        grid_candidates=(12, 24),
        narrow_voice_limit=4,
        wide_voice_limit=5,
        bass_range=(33, 57),
        inner_range=(52, 82),
        melody_range=(67, 100),
        inner_center=69,
        inner_spread=6,
        min_bass_gap=10,
        min_inner_gap=3,
        max_inner_gap=14,
        low_cluster_cutoff=59,
        strong_accent=8,
        medium_accent=4,
        weak_accent=-1,
        bass_velocity_bonus=5,
        melody_velocity_bonus=7,
        extension_duplicate_penalty=22,
    ),
    "classical": StyleProfile(
        slug="classical",
        label="Classical",
        description="Tighter four-part spacing with conservative extensions and smoother voice leading.",
        priority_order=(0, 1, 4, 2, 3),
        duplicate_order=(0, 1, 4),
        grid_candidates=(24, 12),
        narrow_voice_limit=4,
        wide_voice_limit=4,
        bass_range=(40, 60),
        inner_range=(55, 76),
        melody_range=(64, 88),
        inner_center=67,
        inner_spread=4,
        min_bass_gap=7,
        min_inner_gap=2,
        max_inner_gap=9,
        low_cluster_cutoff=62,
        strong_accent=6,
        medium_accent=3,
        weak_accent=-1,
        bass_velocity_bonus=3,
        melody_velocity_bonus=4,
        extension_duplicate_penalty=30,
    ),
    "jazz": StyleProfile(
        slug="jazz",
        label="Jazz",
        description="Root-light inner movement with stronger sevenths and ninths where available.",
        priority_order=(0, 2, 1, 3, 4),
        duplicate_order=(0, 3, 1),
        grid_candidates=(12, 24),
        narrow_voice_limit=4,
        wide_voice_limit=5,
        bass_range=(34, 53),
        inner_range=(50, 78),
        melody_range=(67, 96),
        inner_center=66,
        inner_spread=4,
        min_bass_gap=9,
        min_inner_gap=2,
        max_inner_gap=10,
        low_cluster_cutoff=58,
        strong_accent=5,
        medium_accent=2,
        weak_accent=-3,
        bass_velocity_bonus=3,
        melody_velocity_bonus=5,
        extension_duplicate_penalty=18,
    ),
    "pop": StyleProfile(
        slug="pop",
        label="Pop",
        description="Lean voicings with stable roots, catchy top notes, and cleaner hook-friendly spacing.",
        priority_order=(0, 1, 3, 4, 2),
        duplicate_order=(0, 4, 1),
        grid_candidates=(12, 24),
        narrow_voice_limit=3,
        wide_voice_limit=4,
        bass_range=(36, 57),
        inner_range=(55, 77),
        melody_range=(65, 92),
        inner_center=68,
        inner_spread=5,
        min_bass_gap=10,
        min_inner_gap=3,
        max_inner_gap=12,
        low_cluster_cutoff=60,
        strong_accent=7,
        medium_accent=4,
        weak_accent=-1,
        bass_velocity_bonus=4,
        melody_velocity_bonus=6,
        extension_duplicate_penalty=26,
    ),
}
STYLE_NAMES = tuple(STYLE_PROFILES)
EDITING_STRENGTHS = ("gentle", "balanced", "strong")


@dataclass(frozen=True)
class InstrumentProfile:
    slug: str
    label: str
    description: str
    voicing_mode: str
    narrow_voice_delta: int = 0
    wide_voice_delta: int = 0
    bass_range_shift: tuple[int, int] = (0, 0)
    inner_range_shift: tuple[int, int] = (0, 0)
    melody_range_shift: tuple[int, int] = (0, 0)
    inner_center_shift: int = 0
    inner_spread_delta: int = 0
    min_bass_gap_delta: int = 0
    min_inner_gap_delta: int = 0
    max_inner_gap_delta: int = 0


INSTRUMENT_PROFILES: dict[str, InstrumentProfile] = {
    "harmony": InstrumentProfile(
        slug="harmony",
        label="Harmony",
        description="General harmonic treatment for chord stacks, pads, and voicing cleanup.",
        voicing_mode="harmonic",
    ),
    "keys": InstrumentProfile(
        slug="keys",
        label="Keys",
        description="Keyboard-aware spacing with stronger left/right hand separation.",
        voicing_mode="harmonic",
        narrow_voice_delta=1,
        wide_voice_delta=1,
        bass_range_shift=(-5, -1),
        inner_range_shift=(0, 4),
        melody_range_shift=(2, 4),
        inner_center_shift=1,
        inner_spread_delta=3,
        min_bass_gap_delta=4,
        min_inner_gap_delta=1,
        max_inner_gap_delta=5,
    ),
    "melody": InstrumentProfile(
        slug="melody",
        label="Melody",
        description="Lead-oriented cleanup with mostly monophonic phrasing and stronger top-line continuity.",
        voicing_mode="melodic",
    ),
}
INSTRUMENT_FAMILY_NAMES = tuple(INSTRUMENT_PROFILES)


@dataclass(frozen=True)
class VoiceRole:
    kind: str
    pitch_class: int
    chord_slot: int | None
    inner_index: int = 0
    inner_count: int = 0


@dataclass(frozen=True)
class VoiceCandidate:
    pitch: int
    velocity: int


@dataclass(frozen=True)
class MidiFixOptions:
    style: str = "balanced"
    instrument_family: str = "harmony"
    editing_strength: str = "balanced"
    output_format: int = 1
    include_track_titles: bool = False


@dataclass(frozen=True)
class MidiFixStats:
    style: str
    instrument_family: str
    editing_strength: str
    expression_preserved: bool
    detected_key_center: str
    quantize_grid: int
    output_format: int
    include_track_titles: bool
    original_note_count: int
    cleaned_note_count: int
    edited_note_count: int
    original_pitch_range: tuple[int, int]
    edited_pitch_range: tuple[int, int]
    average_original_duration: float
    average_edited_duration: float


@dataclass(frozen=True)
class MidiFixResult:
    midi_bytes: bytes
    output_filename: str
    source_title: str | None
    edited_title: str
    stats: MidiFixStats


def list_style_names() -> tuple[str, ...]:
    return STYLE_NAMES


def list_instrument_family_names() -> tuple[str, ...]:
    return INSTRUMENT_FAMILY_NAMES


def get_style_profile(style: str) -> StyleProfile:
    key = (style or "balanced").strip().lower()
    if key not in STYLE_PROFILES:
        allowed = ", ".join(STYLE_NAMES)
        raise ValueError(f"Unsupported style '{style}'. Choose one of: {allowed}.")
    return STYLE_PROFILES[key]


def get_instrument_profile(instrument_family: str) -> InstrumentProfile:
    key = (instrument_family or "harmony").strip().lower()
    if key not in INSTRUMENT_PROFILES:
        allowed = ", ".join(INSTRUMENT_FAMILY_NAMES)
        raise ValueError(
            f"Unsupported instrument family '{instrument_family}'. Choose one of: {allowed}."
        )
    return INSTRUMENT_PROFILES[key]


def shift_pitch_range(pitch_range: tuple[int, int], delta: tuple[int, int]) -> tuple[int, int]:
    low = clamp(pitch_range[0] + delta[0], 24, 107)
    high = clamp(pitch_range[1] + delta[1], low + 1, 108)
    return (low, high)


def apply_instrument_profile(
    profile: StyleProfile,
    instrument_profile: InstrumentProfile,
) -> StyleProfile:
    if instrument_profile.voicing_mode != "harmonic" or instrument_profile.slug == "harmony":
        return profile

    narrow_voice_limit = max(1, min(6, profile.narrow_voice_limit + instrument_profile.narrow_voice_delta))
    wide_voice_limit = max(
        narrow_voice_limit,
        min(6, profile.wide_voice_limit + instrument_profile.wide_voice_delta),
    )
    min_bass_gap = max(4, profile.min_bass_gap + instrument_profile.min_bass_gap_delta)
    min_inner_gap = max(1, profile.min_inner_gap + instrument_profile.min_inner_gap_delta)
    max_inner_gap = max(min_inner_gap + 1, profile.max_inner_gap + instrument_profile.max_inner_gap_delta)

    return replace(
        profile,
        narrow_voice_limit=narrow_voice_limit,
        wide_voice_limit=wide_voice_limit,
        bass_range=shift_pitch_range(profile.bass_range, instrument_profile.bass_range_shift),
        inner_range=shift_pitch_range(profile.inner_range, instrument_profile.inner_range_shift),
        melody_range=shift_pitch_range(profile.melody_range, instrument_profile.melody_range_shift),
        inner_center=clamp(profile.inner_center + instrument_profile.inner_center_shift, 36, 96),
        inner_spread=max(2, profile.inner_spread + instrument_profile.inner_spread_delta),
        min_bass_gap=min_bass_gap,
        min_inner_gap=min_inner_gap,
        max_inner_gap=max_inner_gap,
    )


def read_vlq(data: bytes, pos: int) -> tuple[int, int]:
    value = 0
    while True:
        byte = data[pos]
        pos += 1
        value = (value << 7) | (byte & 0x7F)
        if not (byte & 0x80):
            return value, pos


def write_vlq(value: int) -> bytes:
    buffer = [value & 0x7F]
    value >>= 7
    while value:
        buffer.append(0x80 | (value & 0x7F))
        value >>= 7
    return bytes(reversed(buffer))


def pitch_class_name(pitch_class: int) -> str:
    return PITCH_CLASS_NAMES[pitch_class % 12]


def suggest_output_filename(filename: str) -> str:
    source = Path(filename or "upload.mid")
    stem = source.stem or "upload"
    suffix = source.suffix if source.suffix.lower() in {".mid", ".midi"} else ".mid"
    return f"{stem}_edited{suffix}"


def clamp(value: int, low: int, high: int) -> int:
    return max(low, min(high, value))


def sign(value: int) -> int:
    if value > 0:
        return 1
    if value < 0:
        return -1
    return 0


def read_vlq_safe(data: bytes, pos: int, detail: str) -> tuple[int, int]:
    try:
        return read_vlq(data, pos)
    except IndexError as error:
        raise ValueError(detail) from error


def parse_midi_bytes(data: bytes) -> ParsedMidi:
    if data[:4] != b"MThd":
        raise ValueError("Unsupported MIDI file header")
    if len(data) < 14:
        raise ValueError("Incomplete MIDI header")

    try:
        header_len = struct.unpack(">I", data[4:8])[0]
        file_format, tracks_count, division = struct.unpack(">HHH", data[8:14])
    except struct.error as error:
        raise ValueError("Incomplete MIDI header") from error
    if header_len < 6:
        raise ValueError("Malformed MIDI header length")
    if file_format not in (0, 1):
        raise ValueError(f"Unsupported MIDI format: {file_format}")

    pos = 8 + header_len
    if pos > len(data):
        raise ValueError("MIDI header extends past end of file")
    meta_events: list[tuple[int, bytes]] = []
    notes: list[Note] = []
    title: str | None = None

    for _track_index in range(tracks_count):
        if pos + 8 > len(data):
            raise ValueError("Incomplete MIDI track header")
        if data[pos:pos + 4] != b"MTrk":
            raise ValueError("Malformed MIDI track header")
        pos += 4
        try:
            track_len = struct.unpack(">I", data[pos:pos + 4])[0]
        except struct.error as error:
            raise ValueError("Incomplete MIDI track header") from error
        pos += 4
        if pos + track_len > len(data):
            raise ValueError("MIDI track length exceeds file size")
        track = data[pos:pos + track_len]
        pos += track_len

        active: dict[tuple[int, int], list[tuple[int, int]]] = defaultdict(list)
        tick = 0
        cursor = 0
        running_status: int | None = None
        while cursor < len(track):
            delta, cursor = read_vlq_safe(track, cursor, "Unexpected end of MIDI delta-time")
            tick += delta

            if cursor >= len(track):
                raise ValueError("Unexpected end of MIDI event")
            status = track[cursor]
            if status < 0x80:
                if running_status is None:
                    raise ValueError("Running status used before a status byte")
                status = running_status
            else:
                cursor += 1
                running_status = status if status < 0xF0 else None

            if status == 0xFF:
                if cursor >= len(track):
                    raise ValueError("Unexpected end of MIDI meta event")
                meta_type = track[cursor]
                cursor += 1
                length, cursor = read_vlq_safe(track, cursor, "Unexpected end of MIDI meta event")
                if cursor + length > len(track):
                    raise ValueError("MIDI meta event exceeds track length")
                payload = track[cursor:cursor + length]
                cursor += length
                if meta_type == 0x03 and title is None:
                    title = payload.decode("latin1", "replace")
                if meta_type in (0x03, 0x51, 0x58):
                    meta_events.append((tick, bytes([meta_type]) + write_vlq(length) + payload))
                continue

            if status in (0xF0, 0xF7):
                length, cursor = read_vlq_safe(track, cursor, "Unexpected end of MIDI sysex event")
                if cursor + length > len(track):
                    raise ValueError("MIDI sysex event exceeds track length")
                cursor += length
                continue

            event_type = status >> 4
            channel = status & 0x0F
            if event_type in (0x8, 0x9, 0xA, 0xB, 0xE):
                if cursor + 2 > len(track):
                    raise ValueError("Unexpected end of MIDI channel event")
                data1 = track[cursor]
                data2 = track[cursor + 1]
                cursor += 2
                if event_type == 0x9 and data2 > 0:
                    active[(channel, data1)].append((tick, data2))
                elif event_type == 0x8 or (event_type == 0x9 and data2 == 0):
                    if active[(channel, data1)]:
                        start, velocity = active[(channel, data1)].pop(0)
                        if tick > start:
                            notes.append(Note(start, tick, data1, velocity, channel))
            elif event_type in (0xC, 0xD):
                if cursor + 1 > len(track):
                    raise ValueError("Unexpected end of MIDI channel event")
                cursor += 1
            else:
                raise ValueError(f"Unsupported MIDI event type: {event_type}")

    ordered_notes = sorted(notes, key=lambda note: (note.start, note.pitch))
    return ParsedMidi(division=division, meta_events=sorted(meta_events), notes=ordered_notes, title=title)


def scale_pitch_classes(root: int, scale: ScaleProfile) -> set[int]:
    return {(root + interval) % 12 for interval in scale.intervals}


def ordered_scale_pitch_classes(root: int, scale: ScaleProfile) -> list[int]:
    return [((root + interval) % 12) for interval in scale.intervals]


def tonal_center_label(tonal_center: TonalCenter) -> str:
    return f"{pitch_class_name(tonal_center.root)} {tonal_center.scale.label}-like"


def detect_tonal_center(notes: list[Note]) -> TonalCenter:
    pitch_weights: Counter[int] = Counter()
    bass_weights: Counter[int] = Counter()

    max_end = max(note.end for note in notes)
    ending_notes = [note for note in notes if note.end == max_end]
    ending_top_pc = max(ending_notes, key=lambda note: note.pitch).pitch % 12
    ending_bass_pc = min(ending_notes, key=lambda note: note.pitch).pitch % 12

    for note in notes:
        pitch_class = note.pitch % 12
        duration_units = max(1.0, (note.end - note.start) / 24)
        weight = duration_units * (0.45 + note.velocity / 127)
        pitch_weights[pitch_class] += weight
        if note.pitch <= 60:
            bass_weights[pitch_class] += weight * 1.2
        elif note.pitch <= 72:
            bass_weights[pitch_class] += weight * 0.45

    best_center = TonalCenter(root=0, scale=SCALE_PROFILES["major"], score=float("-inf"))
    for root in range(12):
        for scale in SCALE_PROFILES.values():
            scale_pcs = scale_pitch_classes(root, scale)
            ordered_scale = ordered_scale_pitch_classes(root, scale)
            tonic = root
            third = ordered_scale[2]
            dominant = ordered_scale[4]
            leading = ordered_scale[-1]

            score = scale.detection_bias
            for pitch_class, weight in pitch_weights.items():
                score += weight if pitch_class in scale_pcs else -(weight * 1.45)

            score += pitch_weights[tonic] * 0.95
            score += pitch_weights[third] * 0.5
            score += pitch_weights[dominant] * 0.35
            score += bass_weights[tonic] * 0.65
            score += bass_weights[dominant] * 0.18

            if ending_top_pc == tonic:
                score += 2.6
            elif ending_top_pc == third:
                score += 1.2
            elif ending_top_pc == leading:
                score += 0.45

            if ending_bass_pc == tonic:
                score += 3.4
            elif ending_bass_pc == dominant:
                score += 1.3

            center = TonalCenter(root=root, scale=scale, score=score)
            if center.score > best_center.score:
                best_center = center
    return best_center


def snap_to_scale(pitch: int, tonal_center: TonalCenter) -> int:
    allowed = scale_pitch_classes(tonal_center.root, tonal_center.scale)
    if pitch % 12 in allowed:
        return pitch

    candidates: list[tuple[int, int]] = []
    for shift in range(-3, 4):
        candidate = pitch + shift
        if candidate % 12 in allowed:
            candidates.append((abs(shift), candidate))
    if not candidates:
        return pitch
    candidates.sort(key=lambda item: (item[0], abs(item[1] - pitch)))
    return candidates[0][1]


def quantize(value: int, grid: int) -> int:
    return int(round(value / grid) * grid)


def choose_grid(notes: list[Note], profile: StyleProfile) -> int:
    ranked_candidates = list(dict.fromkeys(profile.grid_candidates + (12, 24)))
    best_grid = ranked_candidates[0]
    best_error = float("inf")
    best_rank = len(ranked_candidates)
    for rank, grid in enumerate(ranked_candidates):
        error = 0
        for note in notes:
            error += abs(note.start - quantize(note.start, grid))
            error += abs(note.end - quantize(note.end, grid))
        if error < best_error or (error == best_error and rank < best_rank):
            best_error = error
            best_grid = grid
            best_rank = rank
    return best_grid


def metric_accent(segment_start: int, bar_ticks: int, profile: StyleProfile) -> int:
    metric = segment_start % bar_ticks
    if metric == 0:
        return profile.strong_accent
    if metric % (bar_ticks // 2) == 0:
        return profile.medium_accent
    if metric % (bar_ticks // 4) != 0:
        return profile.weak_accent
    return 0


def clean_notes(
    notes: list[Note],
    grid: int,
    tonal_center: TonalCenter,
    profile: StyleProfile,
    editing_strength: str = "balanced",
) -> list[Note]:
    cleaned: list[Note] = []
    min_duration = grid if profile.slug != "classical" else grid
    for note in notes:
        duration = note.end - note.start
        if duration < grid and note.velocity < 24:
            continue
        if duration < max(1, grid // 2) or note.velocity == 0:
            continue

        start = max(0, _blend_quantize(note.start, grid, editing_strength))
        end = max(start + min_duration, _blend_quantize(note.end, grid, editing_strength))
        pitch = note.pitch if editing_strength == "gentle" else snap_to_scale(note.pitch, tonal_center)
        velocity = _clean_velocity(note.velocity, editing_strength)
        cleaned.append(Note(start, end, pitch, velocity, note.channel))

    cleaned.sort(key=lambda note: (note.start, note.pitch, note.end))

    merged: list[Note] = []
    for note in cleaned:
        if merged:
            previous = merged[-1]
            same_pitch = previous.pitch == note.pitch and previous.channel == note.channel
            close_enough = note.start <= previous.end + max(1, grid // 2)
            if same_pitch and close_enough:
                merged[-1] = Note(
                    previous.start,
                    max(previous.end, note.end),
                    previous.pitch,
                    max(previous.velocity, note.velocity),
                    previous.channel,
                )
                continue
        merged.append(note)
    return merged


def _blend_quantize(value: int, grid: int, strength: str) -> int:
    snapped = quantize(value, grid)
    amount = {"gentle": 0.35, "balanced": 1.0, "strong": 1.0}.get(strength, 1.0)
    return int(round(value + (snapped - value) * amount))


def _clean_velocity(velocity: int, strength: str) -> int:
    if strength == "gentle":
        return min(112, max(18, velocity))
    if strength == "strong":
        return min(100, max(24, velocity))
    return min(92, max(28, velocity))


def build_chromatic_chord_map(
    root: int,
    available_pcs: set[int],
    tonal_center: TonalCenter,
) -> list[int]:
    root %= 12
    scale_pcs = scale_pitch_classes(tonal_center.root, tonal_center.scale)

    def choose(candidates: tuple[int, ...]) -> int:
        normalized = [candidate % 12 for candidate in candidates]
        for candidate in normalized:
            if candidate in available_pcs:
                return candidate
        for candidate in normalized:
            if candidate in scale_pcs:
                return candidate
        return normalized[0]

    third = choose((root + 4, root + 3))
    seventh = choose((root + 10, root + 11))
    ninth = choose((root + 2, root + 1))
    fifth = choose((root + 7, root + 6, root + 8))

    chord_map: list[int] = [root]
    for pitch_class in (third, seventh, ninth, fifth):
        if pitch_class not in chord_map:
            chord_map.append(pitch_class)
    while len(chord_map) < 5:
        chord_map.append((root + (len(chord_map) * 2)) % 12)
    return chord_map[:5]


def get_chord_map(root: int, tonal_center: TonalCenter, available_pcs: set[int] | None = None) -> list[int]:
    ordered_scale = ordered_scale_pitch_classes(tonal_center.root, tonal_center.scale)
    if root in ordered_scale:
        start_index = ordered_scale.index(root)
        stack: list[int] = []
        cursor = start_index
        while len(stack) < 5:
            pitch_class = ordered_scale[cursor % len(ordered_scale)]
            if pitch_class not in stack:
                stack.append(pitch_class)
            cursor += 2
        if len(stack) >= 5:
            return [stack[0], stack[1], stack[3], stack[4], stack[2]]
    return build_chromatic_chord_map(root, available_pcs or set(), tonal_center)


def infer_root(
    active_notes: list[Note],
    tonal_center: TonalCenter,
    previous_root: int | None = None,
) -> int:
    bass_pc = min(active_notes, key=lambda note: note.pitch).pitch % 12
    present = Counter(note.pitch % 12 for note in active_notes)
    scale_pcs = scale_pitch_classes(tonal_center.root, tonal_center.scale)
    available_pcs = set(present)
    candidate_roots = sorted(scale_pcs | available_pcs | {bass_pc})
    best_root = bass_pc
    best_score = float("-inf")
    for root in candidate_roots:
        priority = get_chord_map(root, tonal_center, available_pcs)
        weights = {priority[0]: 5.2, priority[1]: 4.1, priority[2]: 3.0, priority[3]: 1.8, priority[4]: 1.2}
        score = sum(weights.get(pc, 0) * count for pc, count in present.items())
        score += present[root] * 2.2
        if bass_pc == root:
            score += 3.8
        elif bass_pc == priority[-1]:
            score += 1.2
        if previous_root is not None and root == previous_root:
            score += 3.0
            if root in present:
                score += 1.2
        if root == tonal_center.root:
            score += 0.7
        if priority[1] in present:
            score += 0.8
        if priority[2] in present:
            score += 0.6
        if root not in scale_pcs:
            score -= 1.2
        if score > best_score:
            best_score = score
            best_root = root
    return best_root


def role_slot_for_pitch_class(chord_map: list[int], pitch_class: int) -> int | None:
    try:
        return chord_map.index(pitch_class)
    except ValueError:
        return None


def ordered_chord_pitch_classes(
    root: int,
    available_pcs: set[int],
    profile: StyleProfile,
    tonal_center: TonalCenter,
) -> list[int]:
    chord_map = get_chord_map(root, tonal_center, available_pcs)
    ordered: list[int] = []
    for slot in profile.priority_order:
        if slot >= len(chord_map):
            continue
        pitch_class = chord_map[slot]
        if pitch_class in available_pcs and pitch_class not in ordered:
            ordered.append(pitch_class)
    for pitch_class in chord_map:
        if pitch_class in available_pcs and pitch_class not in ordered:
            ordered.append(pitch_class)
    for pitch_class in sorted(available_pcs):
        if pitch_class not in ordered:
            ordered.append(pitch_class)
    return ordered


def desired_voice_count(active_notes: list[Note], profile: StyleProfile) -> int:
    if len(active_notes) <= 2:
        return len(active_notes)
    span = active_notes[-1].pitch - active_notes[0].pitch
    limit = profile.narrow_voice_limit if span < 26 else profile.wide_voice_limit
    available_pcs = len({note.pitch % 12 for note in active_notes})
    return max(3, min(limit, max(available_pcs, min(len(active_notes), available_pcs + 1))))


def choose_duplicate_pitch_class(
    chord_map: list[int],
    available_pcs: set[int],
    current_counts: Counter[int],
    profile: StyleProfile,
    ordered_pcs: list[int],
) -> int:
    for slot in profile.duplicate_order:
        if slot >= len(chord_map):
            continue
        pitch_class = chord_map[slot]
        if pitch_class not in available_pcs:
            continue
        if slot in (2, 3) and current_counts[pitch_class] >= 1:
            continue
        if current_counts[pitch_class] < 2:
            return pitch_class
    for pitch_class in ordered_pcs:
        slot = role_slot_for_pitch_class(chord_map, pitch_class)
        if slot in (2, 3) and current_counts[pitch_class] >= 1:
            continue
        if current_counts[pitch_class] < 2:
            return pitch_class
    return ordered_pcs[0]


def build_role_plan(
    active_notes: list[Note],
    root: int,
    profile: StyleProfile,
    tonal_center: TonalCenter,
) -> list[VoiceRole]:
    available_pcs = {note.pitch % 12 for note in active_notes}
    chord_map = get_chord_map(root, tonal_center, available_pcs)
    detected_bass_pc = active_notes[0].pitch % 12
    bass_slot = role_slot_for_pitch_class(chord_map, detected_bass_pc)
    prefer_root_bass = (
        profile.slug != "jazz"
        and chord_map[0] in available_pcs
        and detected_bass_pc != chord_map[0]
        and bass_slot in (1, 4)
    )
    bass_pc = chord_map[0] if prefer_root_bass else detected_bass_pc
    melody_pc = active_notes[-1].pitch % 12
    ordered_pcs = ordered_chord_pitch_classes(root, available_pcs, profile, tonal_center)
    target_voices = desired_voice_count(active_notes, profile)

    roles: list[VoiceRole] = [
        VoiceRole("bass", bass_pc, role_slot_for_pitch_class(chord_map, bass_pc))
    ]
    current_counts: Counter[int] = Counter({bass_pc: 1})
    inner_slots = max(0, target_voices - 2)
    chosen_inner_pcs: list[int] = []

    essential_pcs = [chord_map[0]]
    if len(chord_map) > 1:
        essential_pcs.append(chord_map[1])
    if len(chord_map) > 4 and profile.slug in {"piano", "balanced"}:
        essential_pcs.append(chord_map[4])
    if len(chord_map) > 2 and profile.slug == "jazz":
        essential_pcs.insert(1, chord_map[2])

    for pitch_class in essential_pcs + ordered_pcs:
        if len(chosen_inner_pcs) >= inner_slots:
            break
        if pitch_class not in available_pcs:
            continue
        if pitch_class == bass_pc and current_counts[pitch_class] >= 1 and target_voices <= 3:
            continue
        if pitch_class == melody_pc and target_voices <= 3:
            continue
        if pitch_class in chosen_inner_pcs:
            continue
        chosen_inner_pcs.append(pitch_class)
        current_counts[pitch_class] += 1

    while len(chosen_inner_pcs) < inner_slots and ordered_pcs:
        duplicate_pc = choose_duplicate_pitch_class(chord_map, available_pcs, current_counts, profile, ordered_pcs)
        chosen_inner_pcs.append(duplicate_pc)
        current_counts[duplicate_pc] += 1

    roles.extend(
        VoiceRole(
            "inner",
            pitch_class,
            role_slot_for_pitch_class(chord_map, pitch_class),
            inner_index=index,
            inner_count=len(chosen_inner_pcs),
        )
        for index, pitch_class in enumerate(chosen_inner_pcs)
    )

    if target_voices > 1:
        roles.append(VoiceRole("melody", melody_pc, role_slot_for_pitch_class(chord_map, melody_pc)))
    return roles


def align_previous_pitches(previous_pitches: tuple[int, ...] | None, roles: list[VoiceRole]) -> list[int | None]:
    if not previous_pitches:
        return [None] * len(roles)

    previous_inner = list(previous_pitches[1:-1]) if len(previous_pitches) > 2 else []
    aligned: list[int | None] = []
    inner_cursor = 0
    for role in roles:
        if role.kind == "bass":
            aligned.append(previous_pitches[0])
        elif role.kind == "melody":
            aligned.append(previous_pitches[-1])
        else:
            if inner_cursor < len(previous_inner):
                aligned.append(previous_inner[inner_cursor])
            elif previous_inner:
                aligned.append(previous_inner[-1])
            else:
                aligned.append(None)
            inner_cursor += 1
    return aligned


def role_pitch_range(profile: StyleProfile, role: VoiceRole) -> tuple[int, int]:
    if role.kind == "bass":
        return profile.bass_range
    if role.kind == "melody":
        return profile.melody_range
    return profile.inner_range


def default_target_pitch(
    profile: StyleProfile,
    role: VoiceRole,
    source_bass_pitch: int,
    source_melody_pitch: int,
) -> int:
    if role.kind == "bass":
        return clamp(source_bass_pitch, *profile.bass_range)
    if role.kind == "melody":
        return clamp(source_melody_pitch, *profile.melody_range)
    if role.inner_count <= 1:
        return profile.inner_center
    spread_offset = role.inner_index - (role.inner_count - 1) / 2
    target = profile.inner_center + int(round(spread_offset * profile.inner_spread))
    return clamp(target, *profile.inner_range)


def generate_role_candidates(
    active_notes: list[Note],
    role: VoiceRole,
    previous_pitch: int | None,
    profile: StyleProfile,
    source_bass_pitch: int,
    source_melody_pitch: int,
) -> list[VoiceCandidate]:
    matching = [note for note in active_notes if note.pitch % 12 == role.pitch_class]
    if not matching:
        return []

    low, high = role_pitch_range(profile, role)
    default_target = default_target_pitch(profile, role, source_bass_pitch, source_melody_pitch)
    target = previous_pitch if previous_pitch is not None else default_target

    candidates_by_pitch: dict[int, int] = {}
    for note in matching:
        for octave in range(-3, 4):
            pitch = note.pitch + octave * 12
            if not 24 <= pitch <= 108:
                continue
            current = candidates_by_pitch.get(pitch)
            if current is None or note.velocity > current:
                candidates_by_pitch[pitch] = note.velocity

    scored: list[tuple[float, int, int]] = []
    for pitch, velocity in candidates_by_pitch.items():
        score = abs(pitch - target)
        if pitch < low:
            score += (low - pitch) * 2.5
        if pitch > high:
            score += (pitch - high) * 2.5
        if role.kind == "bass":
            score += abs(pitch - source_bass_pitch) * 0.25
        elif role.kind == "melody":
            score += abs(pitch - source_melody_pitch) * 0.2
        else:
            score += abs(pitch - default_target) * 0.35
        scored.append((score, pitch, velocity))

    scored.sort(key=lambda item: (item[0], item[1]))
    limit = 5 if role.kind in {"bass", "melody"} else 4
    return [VoiceCandidate(pitch, velocity) for _score, pitch, velocity in scored[:limit]]


def parallel_motion_penalty(previous: list[int | None], current: list[int]) -> float:
    if not previous or len(previous) != len(current):
        return 0.0

    penalty = 0.0
    pairs = [(0, len(current) - 1)]
    pairs.extend((index, index + 1) for index in range(len(current) - 1))
    for first, second in pairs:
        prev_first = previous[first]
        prev_second = previous[second]
        if prev_first is None or prev_second is None:
            continue
        direction_first = sign(current[first] - prev_first)
        direction_second = sign(current[second] - prev_second)
        if direction_first == direction_second == 0:
            continue
        if direction_first != direction_second or direction_first == 0:
            continue
        prev_interval = abs(prev_second - prev_first) % 12
        curr_interval = abs(current[second] - current[first]) % 12
        outer = first == 0 and second == len(current) - 1
        if prev_interval == curr_interval == 0:
            penalty += 26 if outer else 12
        elif prev_interval == curr_interval == 7:
            penalty += 18 if outer else 8
        elif outer and curr_interval in (0, 7):
            penalty += 6
    return penalty


def combination_score(
    combo: tuple[VoiceCandidate, ...],
    roles: list[VoiceRole],
    previous_pitches: list[int | None],
    profile: StyleProfile,
    chord_map: list[int],
    source_bass_pitch: int,
    source_melody_pitch: int,
) -> float:
    pitches = [candidate.pitch for candidate in combo]
    score = 0.0

    for left, right in zip(pitches, pitches[1:]):
        if left >= right:
            return float("inf")

    bass_gap = pitches[1] - pitches[0] if len(pitches) > 1 else profile.min_bass_gap
    if bass_gap < profile.min_bass_gap:
        score += (profile.min_bass_gap - bass_gap) * 12

    for index, (lower, upper) in enumerate(zip(pitches[1:], pitches[2:]), start=1):
        gap = upper - lower
        if gap < profile.min_inner_gap:
            score += (profile.min_inner_gap - gap) * 14
        if gap > profile.max_inner_gap:
            score += (gap - profile.max_inner_gap) * 1.8
        if lower < profile.low_cluster_cutoff and gap <= 2:
            score += 26
        if lower < 64 and gap == 1:
            score += 14
        if index == len(pitches) - 2 and gap > 16:
            score += 4

    for role, candidate, previous_pitch in zip(roles, combo, previous_pitches):
        low, high = role_pitch_range(profile, role)
        if candidate.pitch < low:
            score += (low - candidate.pitch) * 4
        if candidate.pitch > high:
            score += (candidate.pitch - high) * 4
        if previous_pitch is not None:
            movement = abs(candidate.pitch - previous_pitch)
            score += movement * 0.75
            if role.kind == "bass" and movement > 12:
                score += (movement - 12) * 3.2
            if role.kind == "melody" and movement > 12:
                score += (movement - 12) * 3.4
            if role.kind == "inner" and movement > 9:
                score += (movement - 9) * 2.8
            if movement == 0:
                score -= 1.5
        elif role.kind == "inner":
            score += abs(candidate.pitch - profile.inner_center) * 0.1

    score += abs(pitches[0] - source_bass_pitch) * 0.2
    score += abs(pitches[-1] - source_melody_pitch) * 0.15

    role_counts = Counter(role.pitch_class for role in roles)
    for pitch_class, count in role_counts.items():
        if count <= 1:
            continue
        chord_slot = role_slot_for_pitch_class(chord_map, pitch_class)
        if chord_slot in (2, 3):
            score += profile.extension_duplicate_penalty * (count - 1)
        elif chord_slot == 1:
            score += 8 * (count - 1)
        elif chord_slot == 4:
            score += 4 * (count - 1)
        elif chord_slot == 0:
            score -= 2 * (count - 1)

    if len(chord_map) > 1 and chord_map[1] not in role_counts:
        score += 12
    if chord_map[0] not in role_counts:
        score += 16

    score += parallel_motion_penalty(previous_pitches, pitches)

    if previous_pitches and previous_pitches[0] is not None and previous_pitches[-1] is not None:
        bass_dir = sign(pitches[0] - previous_pitches[0])
        melody_dir = sign(pitches[-1] - previous_pitches[-1])
        if bass_dir != 0 and melody_dir != 0 and bass_dir != melody_dir:
            score -= 3

    return score


def shape_velocities(
    combo: tuple[VoiceCandidate, ...],
    roles: list[VoiceRole],
    segment_start: int,
    bar_ticks: int,
    profile: StyleProfile,
) -> list[tuple[int, int]]:
    accent = metric_accent(segment_start, bar_ticks, profile)
    voiced: list[tuple[int, int]] = []
    for role, candidate in zip(roles, combo):
        velocity = candidate.velocity + accent
        if role.kind == "bass":
            velocity += profile.bass_velocity_bonus
        elif role.kind == "melody":
            velocity += profile.melody_velocity_bonus
        elif role.chord_slot in (2, 3) and profile.slug != "jazz":
            velocity -= 2
        voiced.append((candidate.pitch, clamp(velocity, 34, 96)))
    return voiced


def fallback_voicing(
    active_notes: list[Note],
    segment_start: int,
    bar_ticks: int,
    profile: StyleProfile,
) -> list[tuple[int, int]]:
    desired = desired_voice_count(active_notes, profile)
    unique_by_pitch: dict[int, Note] = {}
    for note in active_notes:
        current = unique_by_pitch.get(note.pitch)
        if current is None or note.velocity > current.velocity:
            unique_by_pitch[note.pitch] = note
    ordered = sorted(unique_by_pitch.values(), key=lambda note: note.pitch)
    if len(ordered) > desired:
        keep = [ordered[0]]
        middle = ordered[1:-1]
        while len(keep) < desired - 1 and middle:
            keep.append(middle.pop(len(middle) // 2))
        if desired > 1:
            keep.append(ordered[-1])
        ordered = sorted(keep[:desired], key=lambda note: note.pitch)

    accent = metric_accent(segment_start, bar_ticks, profile)
    result: list[tuple[int, int]] = []
    for index, note in enumerate(ordered):
        velocity = note.velocity + accent
        if index == 0:
            velocity += profile.bass_velocity_bonus
        if index == len(ordered) - 1:
            velocity += profile.melody_velocity_bonus
        result.append((note.pitch, clamp(velocity, 34, 96)))
    return result


def select_segment_voicing(
    active_notes: list[Note],
    segment_start: int,
    bar_ticks: int,
    profile: StyleProfile,
    previous_voicing: tuple[int, ...] | None,
    tonal_center: TonalCenter,
    previous_root: int | None,
) -> tuple[list[tuple[int, int]], int]:
    unique_by_pitch: dict[int, Note] = {}
    for note in active_notes:
        current = unique_by_pitch.get(note.pitch)
        if current is None or note.velocity > current.velocity:
            unique_by_pitch[note.pitch] = note
    notes = sorted(unique_by_pitch.values(), key=lambda note: note.pitch)
    if not notes:
        return ([], previous_root or 0)
    if len(notes) == 1:
        note = notes[0]
        velocity = clamp(note.velocity + profile.strong_accent, 34, 96)
        return ([(note.pitch, velocity)], note.pitch % 12)

    root = infer_root(notes, tonal_center, previous_root)
    chord_map = get_chord_map(root, tonal_center, {note.pitch % 12 for note in notes})
    roles = build_role_plan(notes, root, profile, tonal_center)
    previous_pitches = align_previous_pitches(previous_voicing, roles)
    source_bass_pitch = notes[0].pitch
    source_melody_pitch = notes[-1].pitch

    candidate_sets: list[list[VoiceCandidate]] = []
    for role, previous_pitch in zip(roles, previous_pitches):
        candidates = generate_role_candidates(
            notes,
            role,
            previous_pitch,
            profile,
            source_bass_pitch,
            source_melody_pitch,
        )
        if not candidates:
            return (fallback_voicing(notes, segment_start, bar_ticks, profile), root)
        candidate_sets.append(candidates)

    best_score = float("inf")
    best_combo: tuple[VoiceCandidate, ...] | None = None
    for combo in product(*candidate_sets):
        pitches = [candidate.pitch for candidate in combo]
        if any(left >= right for left, right in zip(pitches, pitches[1:])):
            continue
        score = combination_score(
            combo,
            roles,
            previous_pitches,
            profile,
            chord_map,
            source_bass_pitch,
            source_melody_pitch,
        )
        if score < best_score:
            best_score = score
            best_combo = combo

    if best_combo is None:
        return (fallback_voicing(notes, segment_start, bar_ticks, profile), root)
    return (shape_velocities(best_combo, roles, segment_start, bar_ticks, profile), root)


def reharmonize_texture(
    notes: list[Note],
    division: int,
    grid: int,
    profile: StyleProfile,
    tonal_center: TonalCenter,
) -> list[Note]:
    if not notes:
        return []

    boundaries = sorted({boundary for note in notes for boundary in (note.start, note.end)})
    bar_ticks = division * 4
    onsets_by_tick: dict[int, set[int]] = defaultdict(set)
    for note in notes:
        onsets_by_tick[note.start].add(note.pitch)

    segments: list[tuple[int, int, list[tuple[int, int]]]] = []
    previous_voicing: tuple[int, ...] | None = None
    previous_root: int | None = None
    for start, end in zip(boundaries, boundaries[1:]):
        if end <= start:
            continue
        active = [note for note in notes if note.start < end and note.end > start]
        if not active:
            continue
        voicing, root = select_segment_voicing(
            active,
            start,
            bar_ticks,
            profile,
            previous_voicing,
            tonal_center,
            previous_root,
        )
        segments.append((start, end, voicing))
        previous_voicing = tuple(pitch for pitch, _velocity in voicing)
        previous_root = root

    rebuilt: list[Note] = []
    active_output: dict[int, tuple[int, int]] = {}

    for start, _end, voicing in segments:
        next_voices = {pitch: velocity for pitch, velocity in voicing}
        current_pitches = set(active_output)
        next_pitches = set(next_voices)

        for pitch in sorted(current_pitches - next_pitches):
            note_start, velocity = active_output.pop(pitch)
            if start > note_start:
                rebuilt.append(Note(note_start, start, pitch, velocity))

        for pitch in sorted(current_pitches & next_pitches):
            existing_start, existing_velocity = active_output[pitch]
            should_restrike = pitch in onsets_by_tick[start] and start - existing_start >= grid
            should_revoice = abs(next_voices[pitch] - existing_velocity) >= 10 and start - existing_start >= grid * 2
            if should_restrike or should_revoice:
                rebuilt.append(Note(existing_start, start, pitch, existing_velocity))
                active_output[pitch] = (start, next_voices[pitch])

        for pitch in sorted(next_pitches - current_pitches):
            active_output[pitch] = (start, next_voices[pitch])

    final_tick = boundaries[-1]
    for pitch, (note_start, velocity) in active_output.items():
        if final_tick > note_start:
            rebuilt.append(Note(note_start, final_tick, pitch, velocity))

    rebuilt.sort(key=lambda note: (note.start, note.pitch))
    return rebuilt


def select_melody_note(
    active_notes: list[Note],
    segment_start: int,
    bar_ticks: int,
    profile: StyleProfile,
    previous_pitch: int | None,
) -> tuple[int, int] | None:
    unique_by_pitch: dict[int, Note] = {}
    for note in active_notes:
        current = unique_by_pitch.get(note.pitch)
        current_duration = (current.end - current.start) if current else -1
        duration = note.end - note.start
        if (
            current is None
            or note.velocity > current.velocity
            or (note.velocity == current.velocity and duration > current_duration)
        ):
            unique_by_pitch[note.pitch] = note

    notes = sorted(unique_by_pitch.values(), key=lambda note: note.pitch)
    if not notes:
        return None

    low, high = profile.melody_range
    top_pitch = notes[-1].pitch
    target = previous_pitch if previous_pitch is not None else clamp(top_pitch, low, high)
    best_score = float("inf")
    best_note: Note | None = None
    for note in notes:
        duration = note.end - note.start
        score = abs(note.pitch - target) * (0.5 if previous_pitch is None else 0.8)
        score += max(0, top_pitch - note.pitch) * 0.9
        if note.pitch < low:
            score += (low - note.pitch) * 3.5
        if note.pitch > high:
            score += (note.pitch - high) * 3.5
        if previous_pitch is not None:
            movement = abs(note.pitch - previous_pitch)
            if movement > 5:
                score += (movement - 5) * 1.2
            if movement > 12:
                score += (movement - 12) * 2.5
            if note.pitch < previous_pitch - 9:
                score += 4
        if note.start == segment_start:
            score -= 3.5
        if note.pitch == top_pitch:
            score -= 2.5
        score -= min(duration, bar_ticks) / max(1, bar_ticks)
        if score < best_score:
            best_score = score
            best_note = note

    if best_note is None:
        return None

    velocity = best_note.velocity + metric_accent(segment_start, bar_ticks, profile) + profile.melody_velocity_bonus
    if best_note.start == segment_start:
        velocity += 2
    return (best_note.pitch, clamp(velocity, 38, 100))


def extract_melody_texture(notes: list[Note], division: int, grid: int, profile: StyleProfile) -> list[Note]:
    if not notes:
        return []

    boundaries = sorted({boundary for note in notes for boundary in (note.start, note.end)})
    bar_ticks = division * 4
    onsets_by_tick: dict[int, set[int]] = defaultdict(set)
    for note in notes:
        onsets_by_tick[note.start].add(note.pitch)

    rebuilt: list[Note] = []
    current_pitch: int | None = None
    current_start: int | None = None
    current_velocity: int | None = None
    previous_pitch: int | None = None

    for start, end in zip(boundaries, boundaries[1:]):
        if end <= start:
            continue
        active = [note for note in notes if note.start < end and note.end > start]
        selection = select_melody_note(active, start, bar_ticks, profile, previous_pitch) if active else None

        if selection is None:
            if current_pitch is not None and current_start is not None and start > current_start:
                rebuilt.append(Note(current_start, start, current_pitch, current_velocity or 64))
            current_pitch = None
            current_start = None
            current_velocity = None
            previous_pitch = None
            continue

        pitch, velocity = selection
        if current_pitch is None:
            current_pitch = pitch
            current_start = start
            current_velocity = velocity
        else:
            same_pitch = pitch == current_pitch
            same_velocity_band = current_velocity is not None and abs(velocity - current_velocity) < 10
            segment_age = start - current_start if current_start is not None else 0
            should_restrike = same_pitch and pitch in onsets_by_tick[start] and segment_age >= grid
            if not same_pitch or should_restrike or not same_velocity_band:
                if current_start is not None and start > current_start:
                    rebuilt.append(Note(current_start, start, current_pitch, current_velocity or 64))
                current_pitch = pitch
                current_start = start
                current_velocity = velocity

        previous_pitch = pitch

    final_tick = boundaries[-1]
    if current_pitch is not None and current_start is not None and final_tick > current_start:
        rebuilt.append(Note(current_start, final_tick, current_pitch, current_velocity or 64))

    rebuilt.sort(key=lambda note: (note.start, note.pitch))
    return rebuilt


def encode_track(events: list[tuple[int, int, bytes]]) -> bytes:
    ordered = sorted(events, key=lambda item: (item[0], item[1], item[2]))
    track_bytes = bytearray()
    last_tick = 0
    for tick, _order, payload in ordered:
        track_bytes.extend(write_vlq(tick - last_tick))
        track_bytes.extend(payload)
        last_tick = tick
    return b"MTrk" + struct.pack(">I", len(track_bytes)) + bytes(track_bytes)


def build_meta_track(meta_events: list[tuple[int, bytes]], title: str | None, *, include_title: bool) -> bytes:
    events: list[tuple[int, int, bytes]] = []
    if include_title:
        header_title = (title or "Edited MIDI").encode("latin1", "replace")
        events.append((0, 0, bytes([0xFF, 0x03]) + write_vlq(len(header_title)) + header_title))

    seen_meta_types: set[int] = {0x03} if include_title else set()
    has_tempo = False
    for tick, payload in meta_events:
        meta_type = payload[0]
        if meta_type == 0x51:
            has_tempo = True
        if meta_type in seen_meta_types:
            continue
        seen_meta_types.add(meta_type)
        events.append((tick, 0, bytes([0xFF]) + payload))

    if not has_tempo:
        events.append((0, 0, b"\xFF\x51\x03\x07\xA1\x20"))

    events.append((0, 2, b"\xFF\x2F\x00"))
    return encode_track(events)


def build_note_track(notes: list[Note], title: str | None, *, include_title: bool) -> bytes:
    events: list[tuple[int, int, bytes]] = []
    if include_title:
        header_title = ((title or "Edited MIDI") + " Notes").encode("latin1", "replace")
        events.append((0, 0, bytes([0xFF, 0x03]) + write_vlq(len(header_title)) + header_title))

    for note in notes:
        events.append((note.start, 1, bytes([0x90 | note.channel, note.pitch, note.velocity])))
        events.append((note.end, -1, bytes([0x80 | note.channel, note.pitch, 0])))

    events.append((notes[-1].end if notes else 0, 2, b"\xFF\x2F\x00"))
    return encode_track(events)


def render_midi_bytes(
    division: int,
    meta_events: list[tuple[int, bytes]],
    notes: list[Note],
    title: str | None,
    *,
    output_format: int,
    include_track_titles: bool,
) -> bytes:
    if not notes:
        raise ValueError("No notes left after processing")

    if output_format == 1:
        meta_track = build_meta_track(meta_events, title, include_title=include_track_titles)
        note_track = build_note_track(notes, title, include_title=include_track_titles)
        header = b"MThd" + struct.pack(">IHHH", 6, 1, 2, division)
        return header + meta_track + note_track

    if output_format == 0:
        events: list[tuple[int, int, bytes]] = []
        if include_track_titles:
            header_title = (title or "Edited MIDI").encode("latin1", "replace")
            events.append((0, 0, bytes([0xFF, 0x03]) + write_vlq(len(header_title)) + header_title))

        has_tempo = False
        has_signature = False
        for tick, payload in meta_events:
            meta_type = payload[0]
            if meta_type == 0x51 and not has_tempo:
                events.append((tick, 0, bytes([0xFF]) + payload))
                has_tempo = True
            if meta_type == 0x58 and not has_signature:
                events.append((tick, 0, bytes([0xFF]) + payload))
                has_signature = True
        if not has_tempo:
            events.append((0, 0, b"\xFF\x51\x03\x07\xA1\x20"))

        for note in notes:
            events.append((note.start, 1, bytes([0x90 | note.channel, note.pitch, note.velocity])))
            events.append((note.end, -1, bytes([0x80 | note.channel, note.pitch, 0])))
        events.append((notes[-1].end, 2, b"\xFF\x2F\x00"))
        track = encode_track(events)
        header = b"MThd" + struct.pack(">IHHH", 6, 0, 1, division)
        return header + track

    raise ValueError(f"Unsupported output format: {output_format}")


def _average_duration(notes: list[Note]) -> float:
    if not notes:
        return 0.0
    return round(sum(note.end - note.start for note in notes) / len(notes), 1)


def _pitch_range(notes: list[Note]) -> tuple[int, int]:
    if not notes:
        return (0, 0)
    pitches = [note.pitch for note in notes]
    return (min(pitches), max(pitches))


def build_stats(
    *,
    tonal_center: TonalCenter,
    grid: int,
    options: MidiFixOptions,
    original_notes: list[Note],
    cleaned_notes: list[Note],
    edited_notes: list[Note],
) -> MidiFixStats:
    return MidiFixStats(
        style=options.style,
        instrument_family=options.instrument_family,
        editing_strength=options.editing_strength,
        expression_preserved=options.editing_strength == "gentle",
        detected_key_center=tonal_center_label(tonal_center),
        quantize_grid=grid,
        output_format=options.output_format,
        include_track_titles=options.include_track_titles,
        original_note_count=len(original_notes),
        cleaned_note_count=len(cleaned_notes),
        edited_note_count=len(edited_notes),
        original_pitch_range=_pitch_range(original_notes),
        edited_pitch_range=_pitch_range(edited_notes),
        average_original_duration=_average_duration(original_notes),
        average_edited_duration=_average_duration(edited_notes),
    )


def fix_midi_bytes(
    data: bytes,
    *,
    source_name: str = "upload.mid",
    options: MidiFixOptions | None = None,
) -> MidiFixResult:
    active_options = options or MidiFixOptions()
    if active_options.editing_strength not in EDITING_STRENGTHS:
        raise ValueError(f"Unsupported editing strength: {active_options.editing_strength}")
    style_profile = get_style_profile(active_options.style)
    instrument_profile = get_instrument_profile(active_options.instrument_family)
    profile = apply_instrument_profile(style_profile, instrument_profile)
    parsed = parse_midi_bytes(data)
    if not parsed.notes:
        raise ValueError("The MIDI file does not contain note events")

    tonal_center = detect_tonal_center(parsed.notes)
    grid = choose_grid(parsed.notes, profile)
    cleaned = clean_notes(
        parsed.notes,
        grid=grid,
        tonal_center=tonal_center,
        profile=profile,
        editing_strength=active_options.editing_strength,
    )
    if active_options.editing_strength == "gentle":
        edited = cleaned
    elif instrument_profile.voicing_mode == "melodic":
        edited = extract_melody_texture(cleaned, division=parsed.division, grid=grid, profile=profile)
    else:
        edited = reharmonize_texture(
            cleaned,
            division=parsed.division,
            grid=grid,
            profile=profile,
            tonal_center=tonal_center,
        )

    family_suffix = (
        f"{style_profile.slug}-{instrument_profile.slug}"
        if instrument_profile.slug != "harmony"
        else style_profile.slug
    )
    edited_title = f"{parsed.title or Path(source_name).stem or 'MIDI'} ({family_suffix}-edited)"
    midi_bytes = render_midi_bytes(
        parsed.division,
        parsed.meta_events,
        edited,
        edited_title,
        output_format=active_options.output_format,
        include_track_titles=active_options.include_track_titles,
    )
    stats = build_stats(
        tonal_center=tonal_center,
        grid=grid,
        options=active_options,
        original_notes=parsed.notes,
        cleaned_notes=cleaned,
        edited_notes=edited,
    )
    return MidiFixResult(
        midi_bytes=midi_bytes,
        output_filename=suggest_output_filename(source_name),
        source_title=parsed.title,
        edited_title=edited_title,
        stats=stats,
    )


def fix_midi_file(
    input_path: Path,
    output_path: Path,
    *,
    options: MidiFixOptions | None = None,
) -> MidiFixStats:
    result = fix_midi_bytes(input_path.read_bytes(), source_name=input_path.name, options=options)
    output_path.write_bytes(result.midi_bytes)
    return result.stats
