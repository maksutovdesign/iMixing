from __future__ import annotations

import json
import shutil
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from .mix_strategy import build_project
from .reporting import render_markdown
from .rendering import render_master


JOB_ROOT = Path("/tmp/imixing_jobs")


@dataclass
class AudioJob:
    id: str
    input_dir: Path
    output_dir: Path
    genre: str
    target: str
    status: str = "queued"
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    error: str | None = None
    warnings: list[str] = field(default_factory=list)
    result: dict | None = None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "status": self.status,
            "genre": self.genre,
            "target": self.target,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "error": self.error,
            "warnings": self.warnings,
            "result": self.result,
        }


_jobs: dict[str, AudioJob] = {}
_jobs_lock = threading.Lock()


def create_audio_job(*, genre: str, target: str) -> AudioJob:
    JOB_ROOT.mkdir(parents=True, exist_ok=True)
    job_id = uuid.uuid4().hex
    job_dir = JOB_ROOT / job_id
    input_dir = job_dir / "stems"
    output_dir = job_dir / "out"
    input_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    job = AudioJob(id=job_id, input_dir=input_dir, output_dir=output_dir, genre=genre, target=target)
    with _jobs_lock:
        _jobs[job_id] = job
    return job


def get_audio_job(job_id: str) -> AudioJob | None:
    with _jobs_lock:
        return _jobs.get(job_id)


def render_audio_job(job_id: str) -> None:
    job = get_audio_job(job_id)
    if not job:
        return

    _set_status(job, "running")
    try:
        project = build_project(job.input_dir, job.target)
        result = render_master(project, job.output_dir, "master.wav", genre=job.genre)
        analysis_json = json.dumps(project.to_dict(), indent=2, ensure_ascii=False)
        mix_plan = render_markdown(project)
        (job.output_dir / "analysis.json").write_text(analysis_json, encoding="utf-8")
        (job.output_dir / "mix_plan.md").write_text(mix_plan, encoding="utf-8")
        job.result = {
            "genre": result.genre,
            "filename": "master.wav",
            "sample_rate": project.stems[0].metrics.sample_rate,
            "loudness": {
                "premaster": result.premaster_loudness.to_dict(),
                "master": result.master_loudness.to_dict(),
            },
            "files": {
                "master": f"/api/audio/jobs/{job.id}/files/master",
                "rough": f"/api/audio/jobs/{job.id}/files/rough",
                "mix_plan": f"/api/audio/jobs/{job.id}/files/mix-plan",
                "analysis": f"/api/audio/jobs/{job.id}/files/analysis",
            },
            "stems": [
                {
                    "filename": stem.metrics.filename,
                    "role": stem.role,
                    "duration_seconds": stem.metrics.duration_seconds,
                    "peak_dbfs": stem.metrics.peak_dbfs,
                    "rms_dbfs": stem.metrics.rms_dbfs,
                }
                for stem in project.stems
            ],
        }
        job.warnings = result.warnings
        _set_status(job, "done")
    except Exception as error:  # noqa: BLE001
        job.error = str(error)
        _set_status(job, "failed")


def cleanup_audio_job(job_id: str) -> None:
    with _jobs_lock:
        job = _jobs.pop(job_id, None)
    if job:
        shutil.rmtree(job.input_dir.parent, ignore_errors=True)


def _set_status(job: AudioJob, status: str) -> None:
    job.status = status
    job.updated_at = time.time()
