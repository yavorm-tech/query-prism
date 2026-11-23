"""The migration chain must build an empty database from the baseline and round-trip."""
import os
import subprocess
import sys

import asyncpg
import pytest

from tests.conftest import BACKEND

pytestmark = pytest.mark.integration


def _alembic(*args):
    subprocess.run([sys.executable, "-m", "alembic", *args], cwd=BACKEND, check=True, env=os.environ.copy(),
                   capture_output=True)


async def _schemas_of(tables):
    conn = await asyncpg.connect(os.environ["DATABASE_URL"].replace("postgresql+asyncpg://", "postgresql://"))
    try:
        rows = await conn.fetch("SELECT table_name, table_schema FROM information_schema.tables WHERE table_name = ANY($1)", tables)
    finally:
        await conn.close()
    return {r["table_name"]: r["table_schema"] for r in rows}


async def test_tables_live_in_their_context_schema():
    schemas = await _schemas_of(["users", "topics", "chunks", "query_history", "subscriptions", "audit_log"])
    assert schemas == {"users": "identity", "topics": "workspace", "chunks": "knowledge",
                       "query_history": "retrieval", "subscriptions": "metering", "audit_log": "audit"}


async def test_downgrade_and_upgrade_round_trip():
    _alembic("downgrade", "0002")
    assert (await _schemas_of(["users", "chunks"])) == {"users": "public", "chunks": "public"}
    _alembic("upgrade", "head")
    assert (await _schemas_of(["users", "subscriptions"])) == {"users": "identity", "subscriptions": "metering"}


async def _company_columns() -> set[str]:
    conn = await asyncpg.connect(os.environ["DATABASE_URL"].replace("postgresql+asyncpg://", "postgresql://"))
    try:
        rows = await conn.fetch(
            "SELECT column_name FROM information_schema.columns WHERE table_name = 'companies'"
        )
    finally:
        await conn.close()
    return {r["column_name"] for r in rows}


async def test_deprecated_company_columns_are_dropped_and_restored_on_downgrade():
    assert "plan" not in await _company_columns()
    _alembic("downgrade", "0004")
    assert {"plan", "storage_used_bytes", "max_users"} <= await _company_columns()
    _alembic("upgrade", "head")
    assert "plan" not in await _company_columns()


async def test_reset_links_sent_before_hashing_keep_working(client, register):
    """0009 hashes outstanding reset tokens in place; the raw token in the email still works."""
    co = await register()
    _alembic("downgrade", "0008")
    conn = await asyncpg.connect(os.environ["DATABASE_URL"].replace("postgresql+asyncpg://", "postgresql://"))
    try:
        await conn.execute(
            "INSERT INTO identity.password_reset_tokens (user_id, token, expires_at) "
            "VALUES ($1, 'sent-before-0009', now() + interval '1 hour')",
            co["user_id"],
        )
    finally:
        await conn.close()
    _alembic("upgrade", "head")
    r = await client.post("/auth/reset-password", json={"token": "sent-before-0009", "new_password": "a new good password"})
    assert r.status_code == 204, r.text
