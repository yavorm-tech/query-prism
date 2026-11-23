"""Database-level tenant isolation (migrations 0011 and 0012). The test app connects
as the least-privilege role, like production."""
import asyncpg
import pytest

from app.shared import db
from app.shared.db import get_pool

pytestmark = pytest.mark.integration


async def _company_ids_visible() -> set[str]:
    async with (await get_pool()).acquire() as conn:
        return {str(r["id"]) for r in await conn.fetch("SELECT id FROM companies")}


async def test_scoped_connection_sees_only_its_company(register):
    a, b = await register(), await register()
    assert {a["company_id"], b["company_id"]} <= await _company_ids_visible()   # unscoped: system paths

    db.set_tenant(a["company_id"])
    try:
        assert await _company_ids_visible() == {a["company_id"]}
        async with (await get_pool()).acquire() as conn:
            # A query that forgets its company filter still can't see company B.
            teams = await conn.fetch("SELECT company_id FROM teams")
            subs = await conn.fetch("SELECT company_id FROM subscriptions")
            users = await conn.fetch("SELECT company_id FROM users")
        assert {str(r["company_id"]) for r in teams + subs + users} == {a["company_id"]}
    finally:
        db.set_tenant(None)


async def test_scoped_connection_cannot_write_into_another_company(register):
    a, b = await register(), await register()
    db.set_tenant(a["company_id"])
    try:
        async with (await get_pool()).acquire() as conn:
            with pytest.raises(asyncpg.InsufficientPrivilegeError):      # WITH CHECK
                await conn.execute(
                    "INSERT INTO teams (company_id, name) VALUES ($1, 'sneaky')", b["company_id"],
                )
            # Updating B's rows silently matches nothing.
            assert await conn.execute(
                "UPDATE teams SET name = 'renamed' WHERE company_id = $1", b["company_id"],
            ) == "UPDATE 0"
    finally:
        db.set_tenant(None)


async def test_released_connection_does_not_keep_the_tenant(register):
    a = await register()
    db.set_tenant(a["company_id"])
    async with (await get_pool()).acquire() as conn:
        assert await conn.fetchval("SELECT shared.current_company()::text") == a["company_id"]
    db.set_tenant(None)
    pool = await get_pool()
    for _ in range(pool.get_max_size() + 1):        # cycle through every pooled connection
        async with pool.acquire() as conn:
            assert await conn.fetchval("SELECT shared.current_company()") is None


async def test_requests_are_scoped_to_the_caller_and_leave_nothing_behind(client, register):
    """Every authenticated request runs its queries as the caller's company."""
    from app.main import app
    from fastapi import Depends
    from app.shared.security import get_current_user

    async def probe(user: dict = Depends(get_current_user)):
        async with (await get_pool()).acquire() as conn:
            return {
                "setting": await conn.fetchval("SELECT shared.current_company()::text"),
                "companies": [str(r["id"]) for r in await conn.fetch("SELECT id FROM companies")],
            }

    app.add_api_route("/_test/tenant", probe)
    try:
        a, b = await register(), await register()
        r = await client.get("/_test/tenant", headers=a["headers"])
        assert r.json() == {"setting": a["company_id"], "companies": [a["company_id"]]}
        r = await client.get("/_test/tenant", headers=b["headers"])
        assert r.json()["setting"] == b["company_id"]
        assert db.current_tenant() is None          # nothing leaks out of the request
    finally:
        app.router.routes[:] = [rt for rt in app.router.routes if getattr(rt, "path", "") != "/_test/tenant"]


async def test_cross_tenant_api_access_still_fails(client, register):
    """The application checks still answer 404/403 (RLS is the second line)."""
    a, b = await register(), await register()
    r = await client.post("/ingest", params={"team_id": b["team_id"]},
                          files={"file": ("x.txt", b"hello", "text/plain")}, headers=a["headers"])
    assert r.status_code in (403, 404)


@pytest.mark.parametrize("sql", [
    "DROP TABLE knowledge.chunks",
    "TRUNCATE identity.users",
    "CREATE TABLE identity.evil (id int)",
    "ALTER TABLE identity.users ADD COLUMN evil int",
    "UPDATE audit.audit_log SET event_type = 'x'",
    "DELETE FROM audit.audit_log",
    "SELECT shared.apply_app_grants('qp_app')",
    "SET row_security = off; SELECT 1",
])
async def test_app_role_cannot_change_schema_or_audit_trail(sql, register):
    await register()                                # makes sure the audit log has rows
    async with (await get_pool()).acquire() as conn:
        if sql.startswith("SET row_security"):
            # Turning RLS off is allowed only for roles that bypass it; otherwise queries error.
            db.set_tenant(None)
            await conn.execute("SET row_security = off")
            with pytest.raises(asyncpg.InsufficientPrivilegeError):
                await conn.fetch("SELECT 1 FROM companies LIMIT 1")
            return
        with pytest.raises(asyncpg.InsufficientPrivilegeError):
            await conn.execute(sql)


async def test_app_role_can_append_to_the_audit_log(register):
    co = await register()
    from app.audit.api import log_event
    await log_event(company_id=co["company_id"], event_type="test.appended")
    async with (await get_pool()).acquire() as conn:
        assert await conn.fetchval(
            "SELECT count(*) FROM audit.audit_log WHERE company_id = $1 AND event_type = 'test.appended'",
            co["company_id"],
        ) == 1


async def test_app_role_does_not_bypass_rls():
    async with (await get_pool()).acquire() as conn:
        row = await conn.fetchrow("SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname = current_user")
    assert row["rolsuper"] is False and row["rolbypassrls"] is False


async def test_streamed_responses_keep_the_scope(client, register):
    """SSE answers are produced inside StreamingResponse, in a child task."""
    from app.main import app
    from fastapi import Depends
    from fastapi.responses import StreamingResponse
    from app.shared.security import get_current_user

    async def probe(user: dict = Depends(get_current_user)):
        async def body():
            async with (await get_pool()).acquire() as conn:
                yield str(await conn.fetchval("SELECT shared.current_company()::text"))
        return StreamingResponse(body(), media_type="text/plain")

    app.add_api_route("/_test/tenant-stream", probe)
    try:
        a = await register()
        r = await client.get("/_test/tenant-stream", headers=a["headers"])
        assert r.text == a["company_id"]
    finally:
        app.router.routes[:] = [rt for rt in app.router.routes if getattr(rt, "path", "") != "/_test/tenant-stream"]
