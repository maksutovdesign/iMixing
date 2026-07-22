# MIDI Generator

## Release scope

MIDI Generator creates basslines, melody material, and General MIDI drum-machine parts for projects up to ten minutes. It is a compositional starting point for a DAW, not a claim that it can write a finished song without producer judgment.

## Musical engine

- A style selects a harmonic progression family and rhythmic vocabulary.
- The selected key and major/minor scale constrain chord roots and melody anchor tones.
- Bass follows chord roots, with octave/fifth variation in selected styles.
- Melody can repeat an input motif from MIDI note numbers or derive chord-tone phrases.
- Drums use channel 10 / MIDI channel 9 with kick, snare, closed hats, ghost hats, and section-end fills.
- Swing moves alternating subdivisions; humanize adds seeded micro-timing and velocity variation.
- A seed makes the result reproducible, so users can return to a version later.
- `song` arrangement mode changes energy over intro, verse, chorus, bridge, and outro instead of repeating one loop with identical density.

## Controls

| Control | Range / values |
| --- | --- |
| BPM | 40–240 |
| Duration | 4–600 seconds |
| Key | C through B including sharps/flats supported by the UI |
| Scale | major, minor |
| Style | pop, rap, trap, house, techno, EDM, rock, cinematic, jazz |
| Swing | 0.00–0.50 |
| Humanize | 0.00–1.00 |
| Density | 0.10–1.00 |
| Parts | bass, melody, drums in any combination |
| Motif | comma-separated MIDI note numbers, for example `60, 64, 67` |
| Arrangement | `loop` for a stable pattern, `song` for section-based energy changes |

## Safety rules

- Generation is deterministic for a given seed and settings.
- Output never exceeds 10 minutes and all notes use valid MIDI pitch, velocity, and timing ranges.
- At least one part must be selected.
- The generator does not overwrite uploaded MIDI: it always emits a new downloadable `.mid` file.
- The UI renders its piano roll only from notes parsed from the generated file; it is not a decorative placeholder.
- Recent settings and seeds are kept only in the current browser's local storage, up to six variants.

## Next milestones

1. Piano roll editor with per-section regeneration.
2. Computer-keyboard note entry in addition to physical Web MIDI capture.
3. User chord-progressions and time signatures.
4. Separate MIDI tracks with program changes and DAW templates.
5. Drum Doctor integration for groove extraction, custom kits, fills, and ghost-note editing.
