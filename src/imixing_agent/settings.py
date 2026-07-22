from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _env_int(name: str, default: int, *, minimum: int = 1, maximum: int | None = None) -> int:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    if value < minimum:
        return default
    if maximum is not None and value > maximum:
        return maximum
    return value


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name, "").strip().lower()
    if not raw:
        return default
    return raw in {"1", "true", "yes", "on"}


def _env_path(name: str, default: str) -> Path:
    return Path(os.getenv(name, default)).expanduser()


@dataclass(frozen=True)
class AppSettings:
    environment: str = os.getenv("IMIXING_ENV", "development")
    database_url: str = os.getenv("IMIXING_DATABASE_URL", "sqlite:////tmp/imixing_app.db")
    job_root: Path = _env_path("IMIXING_JOB_ROOT", "/tmp/imixing_jobs")
    max_audio_upload_mb: int = _env_int("IMIXING_MAX_AUDIO_UPLOAD_MB", 250, minimum=1, maximum=2048)
    max_audio_stems: int = _env_int("IMIXING_MAX_AUDIO_STEMS", 24, minimum=1, maximum=128)
    max_audio_duration_seconds: int = _env_int("IMIXING_MAX_AUDIO_DURATION_SECONDS", 600, minimum=10, maximum=7200)
    max_midi_upload_mb: int = _env_int("IMIXING_MAX_MIDI_UPLOAD_MB", 10, minimum=1, maximum=256)
    free_demo_credits: int = _env_int("IMIXING_FREE_DEMO_CREDITS", 5, minimum=0, maximum=10000)
    midi_credit_cost: int = _env_int("IMIXING_MIDI_CREDIT_COST", 1, minimum=0, maximum=10000)
    audio_credit_cost: int = _env_int("IMIXING_AUDIO_CREDIT_COST", 5, minimum=0, maximum=10000)
    credit_cookie_name: str = os.getenv("IMIXING_CREDIT_COOKIE", "imixing_credit_session")
    auth_cookie_name: str = os.getenv("IMIXING_AUTH_COOKIE", "imixing_auth_session")
    auth_session_days: int = _env_int("IMIXING_AUTH_SESSION_DAYS", 30, minimum=1, maximum=365)
    queue_backend: str = os.getenv("IMIXING_QUEUE_BACKEND", "background")
    storage_backend: str = os.getenv("IMIXING_STORAGE_BACKEND", "local")
    storage_root: Path = _env_path("IMIXING_STORAGE_ROOT", "/tmp/imixing_storage")
    storage_bucket: str = os.getenv("IMIXING_STORAGE_BUCKET", "").strip()
    storage_endpoint_url: str = os.getenv("IMIXING_STORAGE_ENDPOINT_URL", "").strip()
    storage_region: str = os.getenv("IMIXING_STORAGE_REGION", "auto").strip() or "auto"
    public_base_url: str = os.getenv("IMIXING_PUBLIC_BASE_URL", "").rstrip("/")
    sentry_dsn: str = os.getenv("SENTRY_DSN", "").strip()
    analytics_enabled: bool = _env_bool("IMIXING_ANALYTICS_ENABLED", True)
    debug: bool = _env_bool("IMIXING_DEBUG", False)

    @property
    def max_audio_upload_bytes(self) -> int:
        return self.max_audio_upload_mb * 1024 * 1024

    @property
    def max_midi_upload_bytes(self) -> int:
        return self.max_midi_upload_mb * 1024 * 1024

    @property
    def auth_session_seconds(self) -> int:
        return self.auth_session_days * 24 * 60 * 60

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite:///")


def load_settings() -> AppSettings:
    return AppSettings()
