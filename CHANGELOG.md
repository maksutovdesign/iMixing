# Changelog

## Unreleased - Generator 2.1

- Added `loop` and `song` arrangement modes; song mode shapes intro, verse, chorus, bridge, and outro energy.
- Added generator presets, reproducible variant history, and one-click restore of saved settings and seed.
- Added a piano-roll preview built from the MIDI that was actually returned by the API, plus a short browser synth preview.
- Added coverage for song arrangement metadata and the public generator API.

## v0.2.0 - MIDI Generator

- Added MIDI Generator as a new iMixing product tab.
- Generates rule-based bassline, melody, and GM drum-machine MIDI up to 10 minutes.
- Added BPM, key, scale, style, swing, humanize, density, selected parts, motif, and deterministic seed controls.
- Added Web MIDI capture for a physical MIDI keyboard in supported browsers.
- Added API endpoint `POST /api/midi/generate`.
- Added content-aware audio diagnostics and expressive MIDI repair modes from the V2 foundation work.

## v0.1.0-beta

- Initial iMixing beta with MIDI Doctor and Mix & Master.
