# iMixing Agent

![iMixing preview](marketing_assets/presentation/imixing-presentation-preview.png)

iMixing Agent is a prototype agent for mixing and mastering separated music stems. A user provides separate tracks such as drums, bass, vocals, guitars, keys, or effects. The agent analyzes every stem, builds an instrument-aware processing chain, prepares a mix strategy, and produces a final mastering plan.

This repository starts with a practical MVP: an offline analysis, mix-plan generator, and real audio renderer for WAV stems.

It now also includes a MIDI repair MVP that can clean timing, simplify voicings, rebalance note density, and export a more DAW-friendly `.mid`.

## Project Summary

iMixing is an AI-assisted music production service for helping musicians move faster from rough material to a cleaner working result. The product is built around a simple promise: upload stems or MIDI, get analysis, repair, processing, and exportable files that are easier to continue in a DAW.

The service does not try to replace the producer, songwriter, or mix engineer. It focuses on the first technical layer that slows people down: rough stems that fight each other, muddy demo balance, noisy MIDI, crowded voicings, unstable velocity, and files that need cleanup before serious arrangement or release work can continue.

Core product directions:

- `Mix & Master`: upload separated WAV stems, detect track roles, analyze levels and clipping, render a processed stereo mix, apply a basic master bus, and export `master.wav`.
- `MIDI Doctor`: upload `.mid` or `.midi`, choose a musical profile, repair timing, voicing density, note ranges, velocity, weak notes, and DAW compatibility.

Primary audience:

- bedroom producers and beatmakers who need quick demo polish;
- songwriters and vocalists who want a better rough version before studio work;
- producers working with MIDI sketches, packs, and collaborator files;
- small studios that need fast pre-processing before manual revisions;
- music schools and creator communities that can use before/after examples for education.

Useful project documents:

- [Project presentation in Russian](docs/PROJECT_PRESENTATION_RU.md)
- [Marketing playbook](docs/MARKETING_PLAYBOOK_2026-05-30.md)
- [Service description](docs/SERVICE_DESCRIPTION.md)
- [Agent specification](docs/AGENT_SPEC.md)

## What The Agent Does

1. Accepts a folder with separated audio stems.
2. Detects the likely role of every stem from its filename.
3. Reads WAV metadata and basic signal metrics.
4. Builds a per-track processing chain.
5. Creates a full mix plan with gain staging, EQ, compression, spatial placement, bus routing, and mastering targets.
6. Renders a processed stereo WAV master.
7. Saves a machine-readable JSON report and a human-readable Markdown plan.

## Recommended Stem Names

Use clear names so the agent can infer each role:

- `drums.wav`
- `kick.wav`
- `snare.wav`
- `bass.wav`
- `lead_vocal.wav`
- `backing_vocals.wav`
- `guitar.wav`
- `piano.wav`
- `synth.wav`
- `fx.wav`

## Quick Start

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
imixing-agent /path/to/your-stems --output out
```

`examples/stems` is only a placeholder folder in the repo. Put your own `.wav` stems in a real directory before running the audio CLI.

## MIDI Repair MVP

For users, the simplest entry point is the local web app:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
imixing-midi-web
```

Then open [http://127.0.0.1:8000](http://127.0.0.1:8000), drag in a MIDI file, choose a musical style and output format, and download the repaired version.

To run on a custom port locally:

```bash
PORT=8010 imixing-midi-web
```

If you intentionally want to expose the local service to other devices on your network, set the host explicitly:

```bash
HOST=0.0.0.0 PORT=8010 imixing-midi-web
```

For CLI usage:

```bash
imixing-midi-fix input.mid output.mid
```

Useful flags:

- `--style balanced|piano|classical|jazz|pop` to choose the musical cleanup profile.
- `--instrument-family harmony|keys|melody` to switch between chord cleanup, keyboard voicing, or lead-line reduction.
- `--output-format 1` for an Ableton-safe multitrack MIDI layout.
- `--output-format 0` for a plain single-track MIDI export.
- `--include-track-titles` if your target DAW or workflow benefits from track name meta-events.

Available styles:

- `balanced` for general-purpose cleanup.
- `piano` for open-handed piano voicings.
- `classical` for tighter four-part motion.
- `jazz` for denser 7th/9th-aware harmony handling.
- `pop` for lean, hook-friendly voicings.

The MIDI fixer currently focuses on:

- quantization cleanup
- note-length normalization
- removal of extremely weak or noisy notes
- style-aware voicing density
- more stable bass and top-line emphasis
- smoother voice leading between chord states
- fewer bad doublings of unstable extensions
- DAW-friendly MIDI export defaults

### Telegram Bot

You can also run the same engine as a Telegram bot:

```bash
export TELEGRAM_BOT_TOKEN=your_bot_token
imixing-midi-telegram
```

Optional environment variables:

- `IMIXING_BOT_STYLE` to set the default style.
- `IMIXING_BOT_FORMAT` to set the default MIDI format (`0` or `1`).

Bot commands:

- `/start`
- `/help`
- `/styles`
- `/style piano`
- `/format 1`
- `/status`

## First Deployment Scenario

The first working deployment path in this repository is Render with a native Python runtime.

Files already prepared for this flow:

- [render.yaml](render.yaml)
- [.python-version](.python-version)
- [docs/DEPLOY_RENDER.md](docs/DEPLOY_RENDER.md)

What this deploy does:

- installs the app with `pip install .`
- starts the public web service with `imixing-midi-web`
- exposes a health check at `/health`
- uses Render's free web-service plan as the initial MVP target

Deployment steps:

1. Push this repo to GitHub, GitLab, or Bitbucket.
2. In Render, create a new Blueprint or Web Service from that repo.
3. If you use Blueprint mode, Render will read `render.yaml` from the repo root.
4. Deploy and wait for the first health check to pass.
5. Open the generated `onrender.com` URL and test a MIDI upload.

Notes:

- Free Render web services can spin down after inactivity, so the first request after idle time may wake the service up more slowly.
- The app is intentionally stateless right now, so no database or persistent disk is required for the first deploy.

## Audio Output

- `out/analysis.json`
- `out/mix_plan.md`
- `out/master.wav`
- `out/master.mp3` when FFmpeg is installed

## Web Audio Jobs

The web app now uses a job-based audio flow for larger stem uploads:

- `POST /api/audio/jobs` uploads WAV stems and creates a render job.
- `GET /api/audio/jobs/{id}` polls job status.
- `GET /api/audio/jobs/{id}/files/master` downloads `master.wav`.
- `GET /api/audio/jobs/{id}/files/rough` downloads `rough_mix.wav`.
- `GET /api/audio/jobs/{id}/files/mix-plan` downloads `mix_plan.md`.
- `GET /api/audio/jobs/{id}/files/analysis` downloads `analysis.json`.

The browser uses this flow for the Mix & Master tab, so large WAV files are no longer returned as base64 JSON in the main UI.

Compatibility note:

- `POST /api/audio/mix` is now a lightweight alias that also returns a `202 Accepted` job reference plus a polling URL instead of embedding WAV/base64 in the response.

To generate reports without rendering audio:

```bash
imixing-agent examples/stems --output out --no-render
```

## Audio Rendering

The renderer uses:

- `soundfile` to load stems and export the final 24-bit WAV master.
- `librosa` to resample stems when sample rates differ.
- `pedalboard` to apply adaptive gain staging, filtering, EQ, compression, reverb, duplicate-stem protection, mix-bus compression, and limiting.
- `pyloudnorm` to measure integrated LUFS for mastering targets.
- `ffmpeg` to export an optional 320 kbps MP3 preview.

Install FFmpeg separately:

```bash
brew install ffmpeg
```

## Current Limitations

- Only uncompressed PCM WAV files are analyzed directly in the current ingest step.
- LUFS is measured with `pyloudnorm`; true peak is approximated with 4x oversampled peak detection.
- The renderer uses practical default chains; it is not a substitute for taste-driven human mix revisions yet.

## Next Milestones

- Add FFmpeg ingest for AIFF, MP3, and FLAC.
- Add deeper DSP chains with parametric EQ, de-essing, saturation, stereo tools, and automation.
- Add beat, key, tempo, transient, and spectral analysis.
- Add genre-specific presets.
- Add reference-track matching.
- Add persistent job storage for uploaded MIDI revisions.
- Add instrument-specific MIDI repair profiles beyond the current style system.
- Add desktop wrapper on top of the same MIDI repair API.
