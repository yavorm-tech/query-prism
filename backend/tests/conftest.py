"""
Test setup.

Unit and architecture tests need nothing. Integration tests need Postgres
(pgvector) and Redis:

    TEST_DATABASE_URL=postgresql://user:pass@host:5432/postgres
    REDIS_URL=redis://host:6379/15

A fresh database (qp_test) is created from postgres/init.sql + `alembic upgrade
head` once per session, so every run exercises the real migration chain.
External AI providers are stubbed; Neo4j is not required (retrieval falls back
to vector-only, which the tests also rely on).
"""
import asyncio
import os
import pathlib
import subprocess
import sys
import uuid

import pytest

BACKEND = pathlib.Path(__file__).resolve().parents[1]
INIT_SQL = BACKEND.parent / "postgres" / "init.sql"
TEST_DB = "qp_test"

os.environ.setdefault("SECRET_KEY", "test-secret-key-" + "x" * 40)
os.environ.setdefault("NEO4J_PASSWORD", "unused-in-tests")
os.environ.setdefault("NEO4J_URL", "bolt://127.0.0.1:1")      # unreachable on purpose
os.environ.setdefault("OPENAI_API_KEY", "sk-test")
os.environ.setdefault("COHERE_API_KEY", "")                  # rerank falls back to similarity
os.environ.setdefault("LOG_LEVEL", "warning")
os.environ.setdefault("UPLOAD_DIR", "/tmp/qp-test-uploads")


def _integration_available() -> bool:
    return bool(os.environ.get("TEST_DATABASE_URL") and os.environ.get("REDIS_URL"))


def _create_test_database() -> str:
    import asyncpg

    admin_url = os.environ["TEST_DATABASE_URL"].replace("postgresql+asyncpg://", "postgresql://")
    test_url = admin_url.rsplit("/", 1)[0] + f"/{TEST_DB}"

    async def recreate():
        conn = await asyncpg.connect(admin_url)
        try:
            await conn.execute(f"DROP DATABASE IF EXISTS {TEST_DB} WITH (FORCE)")
            await conn.execute(f"CREATE DATABASE {TEST_DB}")
        finally:
            await conn.close()
        conn = await asyncpg.connect(test_url)
        try:
            await conn.execute(INIT_SQL.read_text())
        finally:
            await conn.close()

    asyncio.run(recreate())
    return test_url.replace("postgresql://", "postgresql+asyncpg://", 1)


def pytest_configure(config):
    if not _integration_available():
        return
    # Must happen before any app module calls get_settings().
    os.environ["DATABASE_URL"] = _create_test_database()
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=BACKEND, check=True, env=os.environ.copy(),
    )
    import redis
    redis.Redis.from_url(os.environ["REDIS_URL"]).flushdb()


def pytest_collection_modifyitems(config, items):
    if _integration_available():
        return
    skip = pytest.mark.skip(reason="integration: set TEST_DATABASE_URL and REDIS_URL")
    for item in items:
        if "integration" in item.keywords:
            item.add_marker(skip)


# ── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
async def _close_loop_resources():
    # Each test runs on its own loop; close that loop's pools and clients.
    yield
    from app.shared.loop_local import close_loop_resources
    await close_loop_resources()


@pytest.fixture
async def client():
    import httpx
    from app.main import app
    from app.shared.loop_local import close_loop_resources

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app, raise_app_exceptions=False), base_url="http://test") as c:
        yield c
    await close_loop_resources()


@pytest.fixture
def register(client):
    """Sign up a new company through the API; returns its token and ids."""
    from app.shared.security import decode_token

    async def _register(company_name: str | None = None) -> dict:
        tag = uuid.uuid4().hex[:8]
        r = await client.post("/auth/register", json={
            "company_name": company_name or f"Co {tag}",
            "username": f"owner{tag}",
            "email": f"owner{tag}@example.test",
            "password": "correct horse battery",
        })
        assert r.status_code == 201, r.text
        token = r.json()["access_token"]
        claims = decode_token(token)
        return {
            "token": token,
            "headers": {"Authorization": f"Bearer {token}"},
            "company_id": claims["company_id"],
            "team_id": claims["team_ids"][0],
            "user_id": claims["sub"],
            "claims": claims,
        }

    return _register


@pytest.fixture
def ai_stubs(monkeypatch):
    """Deterministic embeddings and answers; no network."""
    import random
    from app.retrieval import router as chat_router, retriever
    from app.shared.ai import embedder

    def vec(seed: str) -> list[float]:
        rnd = random.Random(seed)
        return [rnd.uniform(-1, 1) for _ in range(3072)]

    async def fake_embed(texts):
        return [vec(t) for t in texts]

    async def no_entities(*a, **k):
        from app.shared.ai.ner import ChunkEntities
        return ChunkEntities(chunk_id="query")

    state = {"answer": "stub answer", "fail": False, "llm_calls": 0}

    async def fake_generate(*a, **k):
        state["llm_calls"] += 1
        if state["fail"]:
            raise RuntimeError("provider down")
        return state["answer"]

    async def fake_stream(*a, **k):
        state["llm_calls"] += 1
        if state["fail"]:
            raise RuntimeError("provider down")
        for word in state["answer"].split(" "):
            yield word + " "

    monkeypatch.setattr(embedder, "embed_texts", fake_embed)
    monkeypatch.setattr(retriever, "embed_texts", fake_embed)
    monkeypatch.setattr("app.retrieval.graph_query.extract_entities", no_entities)
    monkeypatch.setattr(chat_router, "generate_answer", fake_generate)
    monkeypatch.setattr(chat_router, "stream_answer", fake_stream)
    state["vec"] = vec
    return state
