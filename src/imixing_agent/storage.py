from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

from .settings import AppSettings


@dataclass(frozen=True)
class StoredObject:
    key: str
    uri: str


class ObjectStorage:
    def put_file(self, source: Path, key: str) -> StoredObject:
        raise NotImplementedError

    def signed_url(self, key: str, *, expires_seconds: int = 3600) -> str:
        raise NotImplementedError


class LocalObjectStorage(ObjectStorage):
    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def put_file(self, source: Path, key: str) -> StoredObject:
        destination = self.root / key
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        return StoredObject(key=key, uri=str(destination))

    def signed_url(self, key: str, *, expires_seconds: int = 3600) -> str:
        return str(self.root / key)


class S3ObjectStorage(ObjectStorage):
    def __init__(self, settings: AppSettings) -> None:
        self.bucket = ""
        self.endpoint = ""
        self.settings = settings

    def put_file(self, source: Path, key: str) -> StoredObject:
        raise RuntimeError(
            "S3/R2 storage backend is configured but not connected yet. "
            "Install and wire boto3 or an S3-compatible client with IMIXING_STORAGE_* env vars."
        )

    def signed_url(self, key: str, *, expires_seconds: int = 3600) -> str:
        raise RuntimeError("S3/R2 signed URLs require a configured storage client.")


def build_storage(settings: AppSettings) -> ObjectStorage:
    if settings.storage_backend.lower() in {"s3", "r2"}:
        return S3ObjectStorage(settings)
    return LocalObjectStorage(settings.storage_root)
