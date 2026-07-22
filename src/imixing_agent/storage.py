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
        if not settings.storage_bucket:
            raise ValueError("IMIXING_STORAGE_BUCKET is required when using an S3/R2 storage backend.")
        try:
            import boto3
        except ModuleNotFoundError as error:
            raise RuntimeError("Install boto3 to use an S3/R2 storage backend.") from error
        self.bucket = settings.storage_bucket
        self.endpoint = settings.storage_endpoint_url
        self.settings = settings
        self.client = boto3.client(
            "s3",
            endpoint_url=settings.storage_endpoint_url or None,
            region_name=settings.storage_region,
        )

    def put_file(self, source: Path, key: str) -> StoredObject:
        normalized_key = key.lstrip("/")
        self.client.upload_file(str(source), self.bucket, normalized_key)
        return StoredObject(key=normalized_key, uri=f"s3://{self.bucket}/{normalized_key}")

    def signed_url(self, key: str, *, expires_seconds: int = 3600) -> str:
        return str(
            self.client.generate_presigned_url(
                "get_object",
                Params={"Bucket": self.bucket, "Key": key.lstrip("/")},
                ExpiresIn=max(60, min(expires_seconds, 7 * 24 * 60 * 60)),
            )
        )


def build_storage(settings: AppSettings) -> ObjectStorage:
    if settings.storage_backend.lower() in {"s3", "r2"}:
        return S3ObjectStorage(settings)
    return LocalObjectStorage(settings.storage_root)
