# iMixing Agent Specification

## Product Goal

The goal is to create an agent that receives separated music tracks, analyzes the musical and technical role of every stem, processes each stem with professional mixing logic, combines them into a balanced stereo mix, and applies final mastering so the user receives a finished track for a music project.

## User Flow

1. User uploads stems.
2. Agent validates format, duration, sample rate, channels, and clipping.
3. Agent classifies stems by role.
4. Agent analyzes levels, dynamics, and stereo information.
5. Agent creates a processing plan for every track.
6. Agent applies track-level processing.
7. Agent routes tracks into buses.
8. Agent creates the stereo mix.
9. Agent masters the mix for the selected target.
10. User downloads the final master plus an optional technical report.

## Core Agent Modules

- `Ingest`: accepts files, validates audio, normalizes project metadata.
- `Analyzer`: extracts duration, peak, RMS, clipping, silence, tempo, key, spectral balance, and dynamics.
- `Stem Classifier`: detects instrument role from filename and audio features.
- `Mix Strategist`: chooses gain, EQ, compression, panning, ambience, and bus routing.
- `Track Processor`: applies instrument-specific processing.
- `Mix Bus Processor`: glues the mix with bus compression, tone shaping, and saturation.
- `Mastering Processor`: final EQ, stereo control, limiting, loudness targeting, and export.
- `Report Generator`: explains what was done and why.

## Stem Processing Standards

### Drums

- Clean low-end rumble where needed.
- Control harsh cymbal frequencies.
- Use transient shaping when drums need more attack.
- Apply parallel compression for weight.
- Route to a drum bus with gentle glue compression.

### Bass

- Remove unnecessary sub-rumble.
- Stabilize dynamics with compression.
- Add harmonic saturation for translation on small speakers.
- Balance low-end relationship with kick.
- Keep the lowest frequencies centered.

### Vocal

- High-pass unnecessary low frequencies.
- Control resonances and harshness.
- Apply compression in stages.
- Add de-essing.
- Use short ambience for depth and longer effects only when stylistically appropriate.
- Keep lead vocal centered and intelligible.

### Guitars And Keys

- Remove masking frequencies against vocal and bass.
- Shape midrange according to arrangement role.
- Use stereo placement to create width without weakening mono compatibility.
- Add ambience based on genre and density.

### Mix Bus

- Preserve headroom before mastering.
- Use subtle compression, tonal EQ, and saturation.
- Avoid clipping before the limiter.

### Mastering

- Correct broad tonal balance.
- Control low-end and harshness.
- Enhance perceived loudness without destroying transients.
- Check mono compatibility.
- Export mastered WAV and optional streaming-ready versions.

## Mastering Targets

- Streaming: about `-14 LUFS integrated`, true peak below `-1 dBTP`.
- Loud modern release: about `-10 to -8 LUFS integrated`, true peak below `-1 dBTP`.
- Club or aggressive electronic: may be louder, but should be selected intentionally.

## Rendering Implementation

The current renderer creates a real stereo master from WAV stems:

- Loads stems with `librosa`.
- Resamples stems to the first stem sample rate.
- Converts mono or multichannel files to stereo.
- Applies role-specific gain staging, high-pass filtering, compression, panning, and light ambience.
- Sums stems into a stereo mix.
- Normalizes premaster headroom.
- Applies mix-bus compression, target gain, and final limiting.
- Exports a 24-bit WAV master with `soundfile`.
- Exports an MP3 preview with `ffmpeg` when available.

## MVP Boundary

The first production version should add more precise loudness measurement, reference-track matching, genre presets, and real-time revision controls. The current renderer is intentionally conservative so it can create a usable first master without pretending that every song needs the same aggressive processing.
