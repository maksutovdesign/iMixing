# Changelog

## Unreleased - Product Workflow 2.3

- Added optional password-protected iMixing accounts, persistent 30-day sessions, and a project library that records new MIDI Doctor, MIDI Generator, and Mix & Master work for signed-in users.
- Added a production-ready S3/R2 adapter with upload and presigned-download support, plus explicit storage and account-session environment variables.
- Added Drum Doctor: a working MIDI cleanup mode for drum patterns that preserves pad pitches, tightens timing, normalizes velocity, and removes duplicate hits.
- Added Mix Console role controls before audio rendering, so automatic role detection can be overridden per uploaded stem.
- Made the shared product header context-aware across MIDI Doctor, Mix & Master, MIDI Generator, and Pricing.
- Fixed the four-tab navigation layout and added coverage for manual mix-role mapping and drum MIDI cleanup.

## v0.2.1 - Generator Workflow

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
