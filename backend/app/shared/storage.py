"""
Upload storage: where files wait between upload (api) and ingestion (worker).

STORAGE_BACKEND=local (default) keeps them in UPLOAD_DIR, a volume the api and
worker containers share, so both must run on one host. STORAGE_BACKEND=s3 keeps
them in an S3-compatible bucket (AWS S3, MinIO, R2, ...), so the api and worker
can run anywhere and the files survive losing a host.

Callers use opaque keys ("<document_id>.<ext>"): put() stores a local file
under a key, local_copy() gives the worker a path to read, delete() removes it.
boto3 is synchronous, so S3 calls run in a thread.
"""
import asyncio
import os
import shutil
import tempfile
from contextlib import contextmanager
from functools import lru_cache
from typing import Iterator, Protocol

from app.shared.config import get_settings


class UploadStorage(Protocol):
    async def put(self, local_path: str, key: str) -> None: ...
    def local_copy(self, key: str): ...          # context manager yielding a readable path
    async def delete(self, key: str) -> None: ...
    def delete_sync(self, key: str) -> None: ...


class LocalStorage:
    def __init__(self, root: str):
        self.root = root

    def path(self, key: str) -> str:
        # Absolute paths are accepted for jobs queued before keys existed.
        return key if os.path.isabs(key) else os.path.join(self.root, key)

    async def put(self, local_path: str, key: str) -> None:
        dest = self.path(key)
        if os.path.abspath(local_path) != os.path.abspath(dest):
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            shutil.move(local_path, dest)

    @contextmanager
    def local_copy(self, key: str) -> Iterator[str]:
        path = self.path(key)
        if not os.path.exists(path):
            raise FileNotFoundError(f"Upload {key} not found")
        yield path

    def delete_sync(self, key: str) -> None:
        try:
            os.remove(self.path(key))
        except FileNotFoundError:
            pass

    async def delete(self, key: str) -> None:
        self.delete_sync(key)


class S3Storage:
    def __init__(self, bucket: str, prefix: str, client):
        self.bucket = bucket
        self.prefix = prefix.strip("/")
        self.client = client

    def _object(self, key: str) -> str:
        name = os.path.basename(key)      # tolerate legacy absolute paths
        return f"{self.prefix}/{name}" if self.prefix else name

    async def put(self, local_path: str, key: str) -> None:
        await asyncio.to_thread(self.client.upload_file, local_path, self.bucket, self._object(key))
        os.remove(local_path)

    @contextmanager
    def local_copy(self, key: str) -> Iterator[str]:
        suffix = os.path.splitext(key)[1]
        fd, path = tempfile.mkstemp(suffix=suffix, prefix="qp-ingest-")
        os.close(fd)
        try:
            self.client.download_file(self.bucket, self._object(key), path)
            yield path
        finally:
            if os.path.exists(path):
                os.remove(path)

    def delete_sync(self, key: str) -> None:
        self.client.delete_object(Bucket=self.bucket, Key=self._object(key))

    async def delete(self, key: str) -> None:
        await asyncio.to_thread(self.delete_sync, key)


@lru_cache
def get_storage() -> UploadStorage:
    s = get_settings()
    if s.storage_backend == "local":
        return LocalStorage(s.upload_dir)
    if s.storage_backend == "s3":
        import boto3
        from botocore.config import Config

        client = boto3.client(
            "s3",
            endpoint_url=s.s3_endpoint_url or None,
            region_name=s.s3_region or None,
            aws_access_key_id=s.s3_access_key_id or None,
            aws_secret_access_key=s.s3_secret_access_key or None,
            config=Config(retries={"max_attempts": 5, "mode": "standard"}),
        )
        return S3Storage(s.s3_bucket, s.s3_prefix, client)
    raise ValueError(f"Unknown STORAGE_BACKEND {s.storage_backend!r}; use 'local' or 's3'")


def spool_dir() -> str:
    """Where the API writes an upload while checking its size, before put()."""
    s = get_settings()
    path = s.upload_dir if s.storage_backend == "local" else os.path.join(tempfile.gettempdir(), "qp-uploads")
    os.makedirs(path, exist_ok=True)
    return path
