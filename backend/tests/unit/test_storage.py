import os

import boto3
import pytest
from moto import mock_aws

from app.shared.storage import LocalStorage, S3Storage


def _file(tmp_path, name="up.txt", data=b"hello"):
    p = tmp_path / name
    p.write_bytes(data)
    return str(p)


async def test_local_storage_round_trip(tmp_path):
    store = LocalStorage(str(tmp_path / "root"))
    await store.put(_file(tmp_path), "doc.txt")
    with store.local_copy("doc.txt") as path:
        assert open(path, "rb").read() == b"hello"
    await store.delete("doc.txt")
    await store.delete("doc.txt")         # deleting twice is fine
    with pytest.raises(FileNotFoundError):
        with store.local_copy("doc.txt"):
            pass


def test_local_storage_accepts_legacy_absolute_paths(tmp_path):
    legacy = _file(tmp_path, "old.txt")
    with LocalStorage("/nonexistent").local_copy(legacy) as path:
        assert path == legacy


async def test_s3_storage_round_trip(tmp_path):
    with mock_aws():
        await _s3_round_trip(tmp_path)


async def _s3_round_trip(tmp_path):
    client = boto3.client("s3", region_name="us-east-1")
    client.create_bucket(Bucket="qp-unit")
    store = S3Storage("qp-unit", "uploads", client)

    src = _file(tmp_path, data=b"x" * 10_000)
    await store.put(src, "doc.pdf")
    assert not os.path.exists(src)                      # spooled copy removed
    assert client.head_object(Bucket="qp-unit", Key="uploads/doc.pdf")["ContentLength"] == 10_000

    with store.local_copy("doc.pdf") as path:
        assert path.endswith(".pdf") and os.path.getsize(path) == 10_000
    assert not os.path.exists(path)                     # temp copy cleaned up

    await store.delete("doc.pdf")
    assert client.list_objects_v2(Bucket="qp-unit").get("KeyCount", 0) == 0
