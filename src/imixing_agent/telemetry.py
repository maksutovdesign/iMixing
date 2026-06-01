from __future__ import annotations

import json
import logging
import sys
import time
from typing import Any

from .settings import AppSettings


LOGGER_NAME = "imixing_agent"


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": round(time.time(), 3),
            "level": record.levelname.lower(),
            "logger": record.name,
            "message": record.getMessage(),
        }
        for key in ("event", "job_id", "session_id", "feature", "status"):
            value = getattr(record, key, None)
            if value is not None:
                payload[key] = value
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def configure_logging(settings: AppSettings) -> logging.Logger:
    logger = logging.getLogger(LOGGER_NAME)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(JsonFormatter())
        logger.addHandler(handler)
    logger.setLevel(logging.DEBUG if settings.debug else logging.INFO)
    logger.propagate = False
    return logger


def configure_sentry(settings: AppSettings, logger: logging.Logger) -> None:
    if not settings.sentry_dsn:
        return
    try:
        import sentry_sdk  # type: ignore
    except ModuleNotFoundError:
        logger.warning("Sentry DSN configured but sentry-sdk is not installed.", extra={"event": "sentry_missing"})
        return
    sentry_sdk.init(dsn=settings.sentry_dsn, environment=settings.environment, traces_sample_rate=0.05)
    logger.info("Sentry initialized.", extra={"event": "sentry_initialized"})


def track_event(
    logger: logging.Logger,
    settings: AppSettings,
    name: str,
    *,
    session_id: str | None = None,
    job_id: str | None = None,
    feature: str | None = None,
    status: str | None = None,
    **properties: Any,
) -> None:
    if not settings.analytics_enabled:
        return
    extra = {
        "event": name,
        "session_id": session_id,
        "job_id": job_id,
        "feature": feature,
        "status": status,
    }
    logger.info(json.dumps(properties, ensure_ascii=False), extra=extra)
