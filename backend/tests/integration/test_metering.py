import asyncio
import collections

import pytest
from fastapi import HTTPException

from app.metering import api as metering
from app.metering import service
from app.shared.db import get_pool

pytestmark = pytest.mark.integration


async def _set(company_id: str, **cols):
    pool = await get_pool()
    sets = ", ".join(f"{k} = ${i + 2}" for i, k in enumerate(cols))
    async with pool.acquire() as conn:
        await conn.execute(f"UPDATE subscriptions SET {sets} WHERE company_id = $1", company_id, *cols.values())


async def _used(company_id: str) -> int:
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetchval("SELECT queries_used_this_month FROM subscriptions WHERE company_id = $1", company_id)


async def test_registration_opens_a_starter_subscription(register):
    co = await register()
    assert await metering.get_plan(co["company_id"]) == "starter"


async def test_concurrent_reserves_never_exceed_the_plan(register):
    co = await register()                                   # starter: 50 queries

    async def attempt():
        try:
            await metering.reserve_query(co["company_id"])
            return "ok"
        except HTTPException as e:
            return e.status_code

    results = collections.Counter(await asyncio.gather(*[attempt() for _ in range(80)]))
    assert results == {"ok": 50, 429: 30}
    assert await _used(co["company_id"]) == 50


async def test_month_rollover_happens_inside_the_reserve(register):
    co = await register()
    await _set(co["company_id"], queries_used_this_month=50)
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE subscriptions SET queries_reset_at = date_trunc('month', now()) - interval '1 month' WHERE company_id = $1",
            co["company_id"],
        )
    assert await metering.reserve_query(co["company_id"]) == "gpt-4o-mini"
    assert await _used(co["company_id"]) == 1


async def test_release_returns_a_query(register):
    co = await register()
    await _set(co["company_id"], queries_used_this_month=50)
    with pytest.raises(HTTPException) as exc:
        await metering.reserve_query(co["company_id"])
    assert exc.value.status_code == 429
    assert exc.value.detail["error"] == "query_limit_reached"
    await metering.release_query(co["company_id"])
    await metering.reserve_query(co["company_id"])


async def test_missing_subscription_is_opened_lazily(register):
    co = await register()
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM subscriptions WHERE company_id = $1", co["company_id"])
    await metering.reserve_query(co["company_id"])
    assert await _used(co["company_id"]) == 1


async def test_usage_report_counts_teams_and_users_through_the_port(client, register):
    co = await register()
    r = await client.get("/usage", headers=co["headers"])
    assert r.status_code == 200
    body = r.json()
    assert body["plan"] == "starter"
    assert body["teams"] == {"used": 1, "limit": 1}
    assert body["users"] == {"used": 1, "limit": 3}


async def test_team_limit_returns_the_plan_message_not_a_server_error(client, register):
    co = await register()                                   # starter allows 1 team
    r = await client.post("/auth/teams", json={"name": "Second"}, headers=co["headers"])
    assert r.status_code == 403
    assert r.json()["detail"]["error"] == "team_limit_reached"


async def test_storage_counter_never_goes_negative(register):
    co = await register()
    await metering.increment_storage(co["company_id"], 100)
    await metering.decrement_storage(co["company_id"], 500)
    row = await service._get_subscription(co["company_id"])
    assert row["storage_used_bytes"] == 0
