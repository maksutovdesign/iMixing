from __future__ import annotations

import logging
import time

from .settings import load_settings
from .telemetry import configure_logging, configure_sentry


def main() -> None:
    settings = load_settings()
    logger = configure_logging(settings)
    configure_sentry(settings, logger)
    logger.info(
        "worker_started",
        extra={"queue_backend": settings.queue_backend, "environment": settings.environment},
    )
    if settings.queue_backend.lower() in {"redis", "rq", "celery"}:
        logger.warning("worker_queue_placeholder", extra={"message": "Wire Redis/RQ or Celery before enabling real background processing."})
    while True:
        time.sleep(60)


if __name__ == "__main__":
    main()
