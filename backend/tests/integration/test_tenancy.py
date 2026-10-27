"""Registration flow and cross-tenant isolation (each test is a hole that existed before)."""
import pytest

from app.shared.db import get_pool

pytestmark = pytest.mark.integration


async def _topic_of(team_id: str) -> dict:
    pool = await get_pool()
    async with pool.acquire() as conn:
        return dict(await conn.fetchrow("SELECT id, name FROM topics WHERE team_id = $1", team_id))


async def test_registration_creates_default_topic_via_event(client, register):
    co = await register()
    topic = await _topic_of(co["team_id"])
    assert topic["name"] == "Main"
    r = await client.get("/auth/me", headers=co["headers"])
    assert r.status_code == 200 and r.json()["plan"] == "starter"


async def test_admin_cannot_list_another_companys_team_members(client, register):
    a, b = await register(), await register()
    r = await client.get(f"/auth/teams/{a['team_id']}/members", headers=b["headers"])
    assert r.status_code == 404


async def test_admin_cannot_remove_member_from_another_companys_team(client, register):
    a, b = await register(), await register()
    r = await client.delete(f"/auth/teams/{a['team_id']}/members/{a['user_id']}", headers=b["headers"])
    assert r.status_code == 404
    r = await client.get(f"/auth/teams/{a['team_id']}/members", headers=a["headers"])
    assert [m["id"] for m in r.json()] == [a["user_id"]]


async def test_admin_cannot_add_a_user_from_another_company(client, register):
    a, b = await register(), await register()
    r = await client.post(f"/auth/teams/{b['team_id']}/members", params={"user_id": a["user_id"]}, headers=b["headers"])
    assert r.status_code == 404


async def test_topics_are_pinned_to_the_callers_company(client, register):
    a, b = await register(), await register()
    topic = await _topic_of(a["team_id"])
    tid = str(topic["id"])
    assert (await client.get(f"/topics/{tid}", headers=b["headers"])).status_code == 404
    assert (await client.patch(f"/topics/{tid}", json={"name": "pwned"}, headers=b["headers"])).status_code == 404
    assert (await client.delete(f"/topics/{tid}", headers=b["headers"])).status_code == 404
    assert (await client.get("/topics", params={"team_id": a["team_id"]}, headers=b["headers"])).status_code == 403
    r = await client.post("/topics", json={"team_id": a["team_id"], "name": "x"}, headers=b["headers"])
    assert r.status_code == 403
    assert (await _topic_of(a["team_id"]))["name"] == "Main"


async def test_document_listing_by_topic_checks_access(client, register):
    a, b = await register(), await register()
    tid = str((await _topic_of(a["team_id"]))["id"])
    assert (await client.get("/ingest", params={"topic_id": tid}, headers=b["headers"])).status_code == 404
    assert (await client.get(f"/topics/{tid}/documents", headers=b["headers"])).status_code == 404
    assert (await client.get(f"/topics/{tid}/questions", headers=b["headers"])).status_code == 404
    assert (await client.get("/ingest", params={"topic_id": tid}, headers=a["headers"])).status_code == 200


async def test_chat_stream_cannot_write_into_another_companys_topic(client, register, ai_stubs):
    a, b = await register(), await register()
    tid = str((await _topic_of(a["team_id"]))["id"])
    r = await client.get("/chat/stream", params={"query": "hi", "topic_id": tid}, headers=b["headers"])
    assert r.status_code == 404
    pool = await get_pool()
    async with pool.acquire() as conn:
        assert await conn.fetchval("SELECT COUNT(*) FROM query_history WHERE topic_id = $1", tid) == 0


async def test_requests_carry_a_request_id(client, register):
    co = await register()
    r = await client.get("/auth/me", headers={**co["headers"], "X-Request-ID": "trace-123"})
    assert r.headers["x-request-id"] == "trace-123"
    assert (await client.get("/health")).json() == {"status": "ok"}
    metrics = (await client.get("/metrics")).text
    assert 'http_requests_total{method="GET",route="/auth/me",status="200"}' in metrics
