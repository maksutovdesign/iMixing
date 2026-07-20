from __future__ import annotations

import io
import math
import struct
import sys
import tempfile
import time
import unittest
import warnings
import wave
from contextlib import redirect_stderr
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

warnings.filterwarnings("ignore", category=DeprecationWarning, module="starlette.testclient")
warnings.filterwarnings("ignore", category=UserWarning, module="starlette.testclient")
warnings.filterwarnings(
    "ignore",
    message=r"Using `httpx` with `starlette\.testclient` is deprecated; install `httpx2` instead\.",
    category=DeprecationWarning,
)
warnings.filterwarnings("ignore", category=DeprecationWarning, module="audioread.rawread")
warnings.filterwarnings(
    "ignore",
    message=r"'.*' is deprecated and slated for removal in Python 3\.13",
    category=DeprecationWarning,
)

from fastapi.testclient import TestClient

from imixing_agent import cli
from imixing_agent.audio_jobs import cleanup_audio_job
from imixing_agent.audio_analysis import analyze_wav
from imixing_agent.loudness import target_true_peak_dbtp
from imixing_agent.quality import detect_mix_conflicts
from imixing_agent.stem_classifier import classify_stem
from imixing_agent.midi_fixer import MidiFixOptions, Note, fix_midi_bytes, parse_midi_bytes, render_midi_bytes
from imixing_agent.midi_generator import MidiGenerationOptions, generate_midi
from imixing_agent.midi_web import app, resolve_host_port
from imixing_agent.mix_strategy import build_project
from imixing_agent.rendering import render_master


def write_sine_wav(path: Path, *, freq: float, duration: float = 1.0, sample_rate: int = 44100) -> None:
    frame_count = int(sample_rate * duration)
    frames = bytearray()
    for index in range(frame_count):
        sample = int(0.2 * 32767 * math.sin(2 * math.pi * freq * index / sample_rate))
        frames.extend(struct.pack("<h", sample))

    with wave.open(str(path), "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(bytes(frames))


def build_test_midi() -> bytes:
    notes = [
        Note(0, 96, 60, 80),
        Note(0, 96, 64, 76),
        Note(0, 96, 67, 72),
        Note(96, 192, 62, 82),
        Note(96, 192, 65, 78),
        Note(96, 192, 69, 74),
    ]
    return render_midi_bytes(96, [], notes, "test", output_format=1, include_track_titles=False)


def build_midi_from_notes(notes: list[Note], title: str = "test") -> bytes:
    return render_midi_bytes(96, [], notes, title, output_format=1, include_track_titles=False)


class MidiHardeningTests(unittest.TestCase):
    def test_midi_generator_creates_all_parts_and_supports_ten_minutes(self) -> None:
        result = generate_midi(
            MidiGenerationOptions(duration_seconds=600, bpm=120, style="house", key="Eb", seed=42)
        )
        parsed = parse_midi_bytes(result.midi_bytes)

        self.assertEqual(result.stats["bars"], 300)
        self.assertGreater(result.stats["note_counts"]["bass"], 0)
        self.assertGreater(result.stats["note_counts"]["melody"], 0)
        self.assertGreater(result.stats["note_counts"]["drums"], 0)
        self.assertIn(9, {note.channel for note in parsed.notes})

    def test_gentle_midi_fix_preserves_pitch_and_most_timing_expression(self) -> None:
        source = build_midi_from_notes([Note(5, 101, 61, 105)], title="live_take")
        result = fix_midi_bytes(
            source,
            source_name="live_take.mid",
            options=MidiFixOptions(editing_strength="gentle", instrument_family="melody"),
        )
        edited = parse_midi_bytes(result.midi_bytes).notes

        self.assertEqual(result.stats.editing_strength, "gentle")
        self.assertTrue(result.stats.expression_preserved)
        self.assertEqual(edited[0].pitch, 61)
        self.assertLess(abs(edited[0].start - 5), 5)
        self.assertEqual(edited[0].velocity, 105)

    def test_fix_midi_bytes_rejects_truncated_midi_as_value_error(self) -> None:
        bad_payloads = [
            b"MThd",
            b"MThd\x00\x00\x00\x06\x00\x01",
            b"MThd\x00\x00\x00\x06\x00\x01\x00\x01\x00\x60MTrk\x00\x00\x00\x01\x00",
        ]

        for payload in bad_payloads:
            with self.assertRaises(ValueError):
                fix_midi_bytes(payload, source_name="broken.mid")

    def test_midi_fix_happy_path_supports_instrument_families(self) -> None:
        source = build_test_midi()
        harmony = fix_midi_bytes(
            source,
            source_name="test.mid",
            options=MidiFixOptions(style="balanced", instrument_family="harmony"),
        )
        melody = fix_midi_bytes(
            source,
            source_name="test.mid",
            options=MidiFixOptions(style="pop", instrument_family="melody"),
        )

        parsed_harmony = parse_midi_bytes(harmony.midi_bytes)
        parsed_melody = parse_midi_bytes(melody.midi_bytes)

        self.assertGreater(len(parsed_harmony.notes), 0)
        self.assertGreater(len(parsed_melody.notes), 0)
        self.assertEqual(harmony.stats.instrument_family, "harmony")
        self.assertEqual(melody.stats.instrument_family, "melody")
        self.assertLess(melody.stats.edited_note_count, harmony.stats.edited_note_count)

    def test_midi_fix_detects_harmonic_minor_and_preserves_leading_tone(self) -> None:
        source = build_midi_from_notes(
            [
                Note(0, 96, 57, 80),
                Note(0, 96, 60, 76),
                Note(0, 96, 64, 72),
                Note(96, 192, 59, 82),
                Note(96, 192, 64, 78),
                Note(96, 192, 68, 74),
            ],
            title="a_harmonic_minor",
        )

        result = fix_midi_bytes(
            source,
            source_name="a_harmonic_minor.mid",
            options=MidiFixOptions(style="balanced", instrument_family="harmony"),
        )
        parsed = parse_midi_bytes(result.midi_bytes)
        pitch_classes = {note.pitch % 12 for note in parsed.notes}

        self.assertEqual(result.stats.detected_key_center, "A harmonic minor-like")
        self.assertIn(8, pitch_classes)
        self.assertNotIn(7, pitch_classes)

    def test_midi_fix_reanchors_accidental_first_inversion_to_root_bass(self) -> None:
        source = build_midi_from_notes(
            [
                Note(0, 96, 60, 80),
                Note(0, 96, 64, 76),
                Note(0, 96, 67, 72),
                Note(96, 192, 64, 80),
                Note(96, 192, 67, 76),
                Note(96, 192, 72, 72),
            ],
            title="c_major_inversion",
        )

        result = fix_midi_bytes(
            source,
            source_name="c_major_inversion.mid",
            options=MidiFixOptions(style="balanced", instrument_family="harmony"),
        )
        parsed = parse_midi_bytes(result.midi_bytes)
        second_segment = [note for note in parsed.notes if note.start == 96]

        self.assertTrue(second_segment)
        self.assertEqual(min(note.pitch for note in second_segment) % 12, 0)


class AudioHardeningTests(unittest.TestCase):
    def test_mastering_target_reads_true_peak_ceiling(self) -> None:
        self.assertEqual(target_true_peak_dbtp("streaming:-14LUFS:-1dBTP"), -1.0)
        self.assertEqual(target_true_peak_dbtp("custom:-12LUFS:-0.3dBTP"), -0.3)

    def test_analyze_wav_rejects_invalid_file_as_value_error(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            path = Path(temp_root) / "broken.wav"
            path.write_bytes(b"RIFF")
            with self.assertRaises(ValueError):
                analyze_wav(path)

    def test_audio_render_happy_path(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            root = Path(temp_root)
            write_sine_wav(root / "kick.wav", freq=60.0)
            write_sine_wav(root / "bass.wav", freq=110.0)

            project = build_project(root, "streaming:-14LUFS:-1dBTP")
            result = render_master(project, root / "out")

            self.assertEqual(len(project.stems), 2)
            self.assertTrue(result.master_path.exists())

    def test_signal_analysis_classifies_unnamed_low_end_stem(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            path = Path(temp_root) / "audio_001.wav"
            write_sine_wav(path, freq=70.0)
            metrics = analyze_wav(path)

        self.assertIsNotNone(metrics.spectral_centroid_hz)
        self.assertGreater(metrics.low_band_ratio or 0.0, 0.9)
        self.assertEqual(classify_stem(path, metrics), "bass")

    def test_mix_quality_detects_kick_bass_masking_risk(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            root = Path(temp_root)
            write_sine_wav(root / "kick.wav", freq=60.0)
            write_sine_wav(root / "bass.wav", freq=80.0)
            project = build_project(root, "streaming:-14LUFS:-1dBTP")

        conflicts = detect_mix_conflicts(project)
        self.assertTrue(any(item["type"] == "low_end_masking" for item in conflicts))


class WebEndpointTests(unittest.TestCase):
    def test_midi_generator_endpoint_returns_downloadable_midi(self) -> None:
        with TestClient(app) as client:
            response = client.post(
                "/api/midi/generate",
                data={
                    "style": "trap",
                    "key": "Eb",
                    "scale": "minor",
                    "bpm": "140",
                    "duration_seconds": "16",
                    "swing": "0.12",
                    "humanize": "0.2",
                    "density": "0.7",
                    "parts": "bass,melody,drums",
                    "seed": "123",
                    "motif": "60,63,67",
                },
            )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["filename"].endswith(".mid"))
        self.assertTrue(payload["midi_base64"])
        self.assertEqual(payload["stats"]["key"], "Eb minor")
        self.assertGreater(payload["stats"]["note_counts"]["drums"], 0)

    def wait_for_audio_job(self, client: TestClient, job_id: str) -> dict:
        payload = {}
        for _ in range(20):
            response = client.get(f"/api/audio/jobs/{job_id}")
            self.assertEqual(response.status_code, 200)
            payload = response.json()
            if payload["status"] == "done":
                return payload
            if payload["status"] == "failed":
                self.fail(payload.get("error", "Audio job failed"))
            time.sleep(0.05)
        self.fail(f"Audio job {job_id} did not finish in time")

    def test_fix_midi_endpoint_returns_400_for_malformed_midi(self) -> None:
        with TestClient(app) as client:
            response = client.post(
                "/api/midi/fix",
                files={"file": ("broken.mid", b"MThd", "audio/midi")},
            )

        self.assertEqual(response.status_code, 400)
        self.assertIn("MIDI", response.json()["detail"])

    def test_audio_jobs_endpoint_returns_400_for_invalid_wav(self) -> None:
        with TestClient(app) as client:
            response = client.post(
                "/api/audio/jobs",
                data={"genre": "balanced", "target": "streaming:-14LUFS:-1dBTP"},
                files=[("files", ("broken.wav", b"RIFF", "audio/wav"))],
            )

        self.assertEqual(response.status_code, 400)
        self.assertIn("WAV", response.json()["detail"])

    def test_audio_jobs_endpoint_returns_download_urls(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            root = Path(temp_root)
            write_sine_wav(root / "kick.wav", freq=60.0)
            write_sine_wav(root / "bass.wav", freq=110.0)

            with TestClient(app) as client:
                with open(root / "kick.wav", "rb") as kick_file, open(root / "bass.wav", "rb") as bass_file:
                    response = client.post(
                        "/api/audio/jobs",
                        data={"genre": "balanced", "target": "streaming:-14LUFS:-1dBTP"},
                        files=[
                            ("files", ("kick.wav", kick_file, "audio/wav")),
                            ("files", ("bass.wav", bass_file, "audio/wav")),
                        ],
                    )
                self.assertEqual(response.status_code, 202)
                payload = response.json()
                self.assertIn("poll_url", payload)

                job_id = payload["id"]
                self.addCleanup(cleanup_audio_job, job_id)
                job = self.wait_for_audio_job(client, job_id)
                self.assertEqual(job["status"], "done")
                self.assertIn("files", job["result"])
                self.assertIn("master", job["result"]["files"])
                self.assertIn("rough", job["result"]["files"])
                self.assertIn("loudness", job["result"])
                self.assertIn("quality", job["result"])
                self.assertIn("status", job["result"]["quality"])
                self.assertIn("mix_conflicts", job["result"]["quality"])

                master_response = client.get(job["result"]["files"]["master"])
                analysis_response = client.get(job["result"]["files"]["analysis"])
                self.assertEqual(master_response.status_code, 200)
                self.assertEqual(analysis_response.status_code, 200)
                self.assertEqual(master_response.headers["content-type"], "audio/wav")
                self.assertIn("application/json", analysis_response.headers["content-type"])

    def test_legacy_audio_mix_endpoint_returns_job_reference(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            root = Path(temp_root)
            write_sine_wav(root / "kick.wav", freq=60.0)

            with TestClient(app) as client:
                with open(root / "kick.wav", "rb") as kick_file:
                    response = client.post(
                        "/api/audio/mix",
                        data={"genre": "balanced", "target": "streaming:-14LUFS:-1dBTP"},
                        files=[("files", ("kick.wav", kick_file, "audio/wav"))],
                    )
                self.assertEqual(response.status_code, 202)
                payload = response.json()
                self.assertIn("poll_url", payload)
                self.assertNotIn("master_base64", payload)
                self.assertIn("async job", payload["detail"])

                self.addCleanup(cleanup_audio_job, payload["id"])

    def test_launch_pages_health_and_icon_are_available(self) -> None:
        with TestClient(app) as client:
            health = client.get("/health")
            icon = client.get("/assets/app-icon.png")
            terms = client.get("/terms")
            privacy = client.get("/privacy")
            early_access = client.get("/early-access")

        self.assertEqual(health.status_code, 200)
        self.assertEqual(health.json()["status"], "ok")
        self.assertIn("queue_backend", health.json())
        self.assertEqual(icon.status_code, 200)
        self.assertIn("image/png", icon.headers["content-type"])
        self.assertEqual(terms.status_code, 200)
        self.assertIn("Terms", terms.text)
        self.assertEqual(privacy.status_code, 200)
        self.assertIn("Privacy", privacy.text)
        self.assertEqual(early_access.status_code, 200)
        self.assertIn("Request access", early_access.text)

    def test_waitlist_endpoint_accepts_beta_signup(self) -> None:
        with TestClient(app) as client:
            response = client.post(
                "/api/waitlist",
                data={
                    "email": "Producer@Example.com",
                    "name": "Test Producer",
                    "role": "producer",
                    "message": "Need mix/master beta access.",
                },
            )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["status"], "ok")
        self.assertTrue(payload["id"])

    def test_audio_jobs_enforces_stem_count_limit_before_processing(self) -> None:
        files = [("files", (f"stem_{index}.wav", b"RIFF", "audio/wav")) for index in range(25)]
        with TestClient(app) as client:
            response = client.post(
                "/api/audio/jobs",
                data={"genre": "balanced", "target": "streaming:-14LUFS:-1dBTP"},
                files=files,
            )

        self.assertEqual(response.status_code, 413)
        self.assertIn("24 stems", response.json()["detail"])

    def test_resolve_host_port_defaults_to_loopback(self) -> None:
        with mock.patch.dict("os.environ", {}, clear=True):
            host, port = resolve_host_port()
        self.assertEqual(host, "127.0.0.1")
        self.assertEqual(port, 8000)

        with mock.patch.dict("os.environ", {"PORT": "8010"}, clear=True):
            host, port = resolve_host_port()
        self.assertEqual(host, "127.0.0.1")
        self.assertEqual(port, 8010)

        with mock.patch.dict("os.environ", {"HOST": "0.0.0.0", "PORT": "8011"}, clear=True):
            host, port = resolve_host_port()
        self.assertEqual(host, "0.0.0.0")
        self.assertEqual(port, 8011)


class CliHardeningTests(unittest.TestCase):
    def test_audio_cli_empty_folder_exits_cleanly(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            stderr = io.StringIO()
            argv = ["imixing-agent", temp_root, "--no-render"]
            with mock.patch.object(sys, "argv", argv):
                with redirect_stderr(stderr):
                    with self.assertRaises(SystemExit) as error:
                        cli.main()

        self.assertEqual(error.exception.code, 2)
        self.assertIn("Analysis failed:", stderr.getvalue())
        self.assertIn("No WAV stems found", stderr.getvalue())
        self.assertNotIn("Traceback", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
