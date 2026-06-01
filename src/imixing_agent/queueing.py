from __future__ import annotations

from collections.abc import Callable
from typing import Any

from fastapi import BackgroundTasks

from .settings import AppSettings


class JobQueue:
    def enqueue(self, background_tasks: BackgroundTasks, fn: Callable[..., Any], *args: Any) -> str:
        raise NotImplementedError


class BackgroundTaskQueue(JobQueue):
    def enqueue(self, background_tasks: BackgroundTasks, fn: Callable[..., Any], *args: Any) -> str:
        background_tasks.add_task(fn, *args)
        return "background"


class InlineQueue(JobQueue):
    def enqueue(self, background_tasks: BackgroundTasks, fn: Callable[..., Any], *args: Any) -> str:
        fn(*args)
        return "inline"


class RedisQueuePlaceholder(JobQueue):
    def enqueue(self, background_tasks: BackgroundTasks, fn: Callable[..., Any], *args: Any) -> str:
        raise RuntimeError(
            "Redis/RQ queue backend is selected but not connected yet. "
            "Provision Redis and wire a worker before setting IMIXING_QUEUE_BACKEND=redis."
        )


def build_queue(settings: AppSettings) -> JobQueue:
    backend = settings.queue_backend.lower()
    if backend == "inline":
        return InlineQueue()
    if backend in {"redis", "rq", "celery"}:
        return RedisQueuePlaceholder()
    return BackgroundTaskQueue()
