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
