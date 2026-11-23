"""Transactional outbox (ADR-010)."""
from dataclasses import dataclass

import pytest

from app.shared import events
from app.shared.db import get_pool

pytestmark = pytest.mark.integration


@dataclass(frozen=True)
class Pinged:
    n: int


@pytest.fixture
def received():
    got = []

    async def handler(event: Pinged):
        got.append(event.n)

    events.subscribe(Pinged, handler)
    yield got
    events._handlers.pop(Pinged, None)


async def _row(event_n: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetchrow(
            "SELECT * FROM shared.outbox WHERE event_type = 'Pinged' AND payload->>'n' = $1", str(event_n),
        )


async def test_event_is_delivered_after_commit(received):
    await events.publish(Pinged(1))
    assert received == [1]
    assert (await _row(1))["processed_at"] is not None


async def test_rolled_back_transaction_publishes_nothing(received):
    with pytest.raises(RuntimeError):
        async with events.unit_of_work() as uow:
            await uow.publish(Pinged(2))
            raise RuntimeError("change failed")
    assert received == [] and await _row(2) is None


async def test_failed_handler_is_retried_by_the_relay():
    calls = []

    async def flaky(event: Pinged):
        calls.append(event.n)
        if len(calls) == 1:
            raise RuntimeError("redis down")

    events.subscribe(Pinged, flaky)
    try:
        await events.publish(Pinged(3))
        row = await _row(3)
        assert row["processed_at"] is None and "redis down" in row["last_error"]

        pool = await get_pool()
        async with pool.acquire() as conn:   # skip the grace period and backoff
            await conn.execute(
                "UPDATE shared.outbox SET created_at = now() - interval '1 hour', available_at = now() WHERE id = $1",
                row["id"],
            )
        await events.relay_once()
        assert calls == [3, 3]
        assert (await _row(3))["processed_at"] is not None
    finally:
        events._handlers.pop(Pinged, None)


async def test_event_is_given_up_after_max_attempts():
    async def broken(event: Pinged):
        raise RuntimeError("always")

    events.subscribe(Pinged, broken)
    try:
        await events.publish(Pinged(4))
        row = await _row(4)
        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.execute("UPDATE shared.outbox SET attempts = $2 WHERE id = $1", row["id"], events.MAX_ATTEMPTS)
        assert await events.deliver(row["id"]) is True     # nothing more to do
    finally:
        events._handlers.pop(Pinged, None)


async def test_default_topic_handler_is_idempotent(client, register):
    co = await register()
    from app.identity.api import CompanyRegistered
    from app.workspace.handlers import create_default_topic
    await create_default_topic(CompanyRegistered(company_id=co["company_id"], team_id=co["team_id"], owner_id=co["user_id"]))
    r = await client.get("/topics", params={"team_id": co["team_id"]}, headers=co["headers"])
    assert [t["name"] for t in r.json()].count("Main") == 1


async def test_failed_sign_up_keeps_nothing(client, monkeypatch):
    """Company, owner, team, subscription and CompanyRegistered commit together or not at all."""
    import uuid
    from app.metering import api as metering

    async def broken(company_id, plan="starter", *, conn=None):
        raise RuntimeError("metering down")
    monkeypatch.setattr(metering, "open_subscription", broken)

    tag = uuid.uuid4().hex[:8]
    r = await client.post("/auth/register", json={
        "company_name": f"Broken {tag}", "username": f"u{tag}",
        "email": f"u{tag}@example.test", "password": "correct horse battery",
    })
    assert r.status_code == 500
    pool = await get_pool()
    async with pool.acquire() as conn:
        assert await conn.fetchval("SELECT COUNT(*) FROM companies WHERE name = $1", f"Broken {tag}") == 0
        assert await conn.fetchval("SELECT COUNT(*) FROM users WHERE email = $1", f"u{tag}@example.test") == 0

    monkeypatch.undo()   # the same email can now sign up normally
    r = await client.post("/auth/register", json={
        "company_name": f"Broken {tag}", "username": f"u{tag}",
        "email": f"u{tag}@example.test", "password": "correct horse battery",
    })
    assert r.status_code == 201, r.text
