import asyncio
import os

import pytest

from app.retrieval import cache
from app.shared.db import get_pool
from app.shared.config import get_settings

pytestmark = pytest.mark.integration


@pytest.fixture
def queued(monkeypatch):
    sent = []

    def send_task(name, args=None, queue=None):
        sent.append((name, args))

        class Result:
            id = "task-1"
        return Result()

    monkeypatch.setattr("app.knowledge.router.celery_app.send_task", send_task)
    monkeypatch.setattr("app.knowledge.tasks.celery_app.send_task", send_task)
    return sent


async def test_upload_size_limit_streams_and_cleans_up(client, register, queued, monkeypatch):
    co = await register()
    monkeypatch.setattr(get_settings(), "max_upload_size_mb", 1)
    r = await client.post("/ingest", params={"team_id": co["team_id"]},
                          files={"file": ("big.txt", os.urandom(2 * 1024 * 1024), "text/plain")}, headers=co["headers"])
    assert r.status_code == 413
    assert not queued
    upload_dir = get_settings().upload_dir
    assert not os.path.isdir(upload_dir) or not os.listdir(upload_dir)


async def _run_worker(document_id: str, path: str):
    # The task runs its own event loop (as in Celery), so it can't run on the test's loop thread.
    return await asyncio.to_thread(_run_worker_sync, document_id, path)


def _run_worker_sync(document_id: str, path: str):
    from app.knowledge.tasks import ingest_document
    from app.shared.celery import celery_app
    celery_app.conf.task_always_eager = True
    celery_app.conf.task_eager_propagates = False
    ingest_document.default_retry_delay = 0
    return ingest_document.apply(args=[document_id, path, "txt"])


async def _doc_state(document_id: str):
    pool = await get_pool()
    async with pool.acquire() as conn:
        status = await conn.fetchval("SELECT status FROM documents WHERE id = $1", document_id)
        chunks = await conn.fetchval("SELECT COUNT(*) FROM chunks WHERE document_id = $1", document_id)
        storage = await conn.fetchval(
            "SELECT s.storage_used_bytes FROM subscriptions s JOIN documents d ON d.company_id = s.company_id WHERE d.id = $1",
            document_id,
        )
    return status, chunks, storage


async def test_worker_retries_with_file_is_idempotent_counts_storage_and_clears_cache(
    client, register, queued, ai_stubs, monkeypatch,
):
    co = await register()
    body = ("Acme Corp signed a contract with Globex in Berlin. " * 4000).encode()
    r = await client.post("/ingest", params={"team_id": co["team_id"]},
                          files={"file": ("ok.txt", body, "text/plain")}, headers=co["headers"])
    assert r.status_code == 200, r.text
    document_id = r.json()["document_id"]
    name, (doc_arg, path, _) = queued[-1]
    assert name == "app.worker.ingest_document" and doc_arg == document_id
    assert os.path.getsize(path) == len(body)

    # A cached answer for this team must disappear once the document is searchable.
    r = await cache.get_redis()
    await r.set("rag:answer:stale", "old")
    await r.sadd(cache._team_index_key(co["team_id"]), "rag:answer:stale")

    from app.knowledge import loaders
    real_load, attempts = loaders.load_document, {"n": 0}

    def flaky(p):
        attempts["n"] += 1
        if attempts["n"] == 1:
            raise RuntimeError("transient OCR failure")
        return real_load(p)
    monkeypatch.setattr(loaders, "load_document", flaky)

    await _run_worker(document_id, path)
    status, chunks, storage = await _doc_state(document_id)
    assert attempts["n"] == 2 and status == "completed" and chunks > 0
    assert storage == len(body)
    assert not os.path.exists(path)
    assert await r.get("rag:answer:stale") is None
    assert queued[-1][0] == "app.graph_worker.build_knowledge_graph"

    # Re-running the same document (late retry) replaces chunks instead of duplicating them.
    with open(path, "wb") as f:
        f.write(body)
    await _run_worker(document_id, path)
    assert (await _doc_state(document_id))[1] == chunks


async def test_worker_marks_failed_only_after_last_attempt(client, register, queued, ai_stubs, monkeypatch):
    co = await register()
    r = await client.post("/ingest", params={"team_id": co["team_id"]},
                          files={"file": ("bad.txt", b"x" * 100, "text/plain")}, headers=co["headers"])
    document_id, path = r.json()["document_id"], queued[-1][1][1]

    from app.knowledge import loaders
    monkeypatch.setattr(loaders, "load_document", lambda p: (_ for _ in ()).throw(RuntimeError("corrupt")))
    await _run_worker(document_id, path)
    status, _, storage = await _doc_state(document_id)
    assert status == "failed" and storage == 0
    assert not os.path.exists(path)

    # Deleting a document that never completed must not reduce storage below what was counted.
    assert (await client.delete(f"/ingest/{document_id}", headers=co["headers"])).status_code == 204
