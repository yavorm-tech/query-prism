"""Short-lived access tokens + rotating refresh cookie (ADR-009)."""
import uuid
from datetime import timedelta

import pytest

from app.identity.tokens import REFRESH_COOKIE, create_access_token
from app.shared.db import get_pool

pytestmark = pytest.mark.integration


async def _signup(client) -> tuple[dict, str]:
    tag = uuid.uuid4().hex[:8]
    client.cookies.clear()
    r = await client.post("/auth/register", json={
        "company_name": f"Co {tag}", "username": f"u{tag}",
        "email": f"u{tag}@example.test", "password": "correct horse battery",
    })
    assert r.status_code == 201, r.text
    return r.json(), r.cookies[REFRESH_COOKIE]


async def _refresh(client, raw: str):
    client.cookies.clear()
    return await client.post("/auth/refresh", headers={"Cookie": f"{REFRESH_COOKIE}={raw}"})


async def test_login_sets_an_httponly_refresh_cookie_and_short_access_token(client):
    body, _ = await _signup(client)
    assert body["expires_in"] == 15 * 60
    r = await client.post("/auth/login", json={"email": "nobody@example.test", "password": "x"})
    assert r.status_code == 401

    tag = uuid.uuid4().hex[:8]
    await client.post("/auth/register", json={
        "company_name": f"Co {tag}", "username": f"v{tag}",
        "email": f"v{tag}@example.test", "password": "correct horse battery",
    })
    r = await client.post("/auth/login", json={"email": f"v{tag}@example.test", "password": "correct horse battery"})
    cookie = r.headers["set-cookie"].lower()
    assert r.status_code == 200
    assert "httponly" in cookie and "samesite=strict" in cookie and "path=/auth" in cookie


async def test_refresh_rotates_and_returns_a_working_access_token(client):
    _, raw = await _signup(client)
    r = await _refresh(client, raw)
    assert r.status_code == 200
    new_raw = r.cookies[REFRESH_COOKIE]
    assert new_raw != raw
    me = await client.get("/auth/me", headers={"Authorization": f"Bearer {r.json()['access_token']}"})
    assert me.status_code == 200


async def test_reusing_a_rotated_token_revokes_the_whole_session(client):
    _, raw = await _signup(client)
    r = await _refresh(client, raw)
    new_raw = r.cookies[REFRESH_COOKIE]

    # Simulate the old token being replayed later than the multi-tab grace window.
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE refresh_tokens SET used_at = used_at - interval '5 minutes' WHERE used_at IS NOT NULL"
        )
    assert (await _refresh(client, raw)).status_code == 401
    # The legitimate holder's newer token is revoked too.
    assert (await _refresh(client, new_raw)).status_code == 401


async def test_concurrent_refresh_within_grace_window_is_not_treated_as_theft(client):
    _, raw = await _signup(client)
    first = await _refresh(client, raw)
    second = await _refresh(client, raw)
    assert first.status_code == 200 and second.status_code == 200
    assert (await _refresh(client, first.cookies[REFRESH_COOKIE])).status_code == 200


async def test_logout_revokes_the_session(client):
    _, raw = await _signup(client)
    client.cookies.clear()
    r = await client.post("/auth/logout", headers={"Cookie": f"{REFRESH_COOKIE}={raw}"})
    assert r.status_code == 204
    assert (await _refresh(client, raw)).status_code == 401


async def test_refresh_without_cookie_is_401(client):
    client.cookies.clear()
    assert (await client.post("/auth/refresh")).status_code == 401


async def test_refresh_picks_up_membership_changes(client, register):
    owner = await register()
    tag = uuid.uuid4().hex[:8]
    r = await client.post("/auth/invite", json={"email": f"m{tag}@example.test", "team_id": owner["team_id"]},
                          headers=owner["headers"])
    invite_token = r.json()["token"]
    client.cookies.clear()
    r = await client.post(f"/auth/invite/{invite_token}/accept", json={"username": f"m{tag}", "password": "correct horse battery"})
    assert r.status_code == 201
    member_raw = r.cookies[REFRESH_COOKIE]

    pool = await get_pool()
    async with pool.acquire() as conn:
        member_id = await conn.fetchval("SELECT id FROM users WHERE email = $1", f"m{tag}@example.test")
    r = await client.delete(f"/auth/teams/{owner['team_id']}/members/{member_id}", headers=owner["headers"])
    assert r.status_code == 204

    r = await _refresh(client, member_raw)
    from app.shared.security import decode_token
    assert decode_token(r.json()["access_token"])["team_ids"] == []


async def test_password_reset_ends_all_sessions(client):
    body, raw = await _signup(client)
    from app.shared.security import decode_token
    user_id = decode_token(body["access_token"])["sub"]
    from app.identity.service import create_password_reset_token
    reset = await create_password_reset_token(user_id)
    async with (await get_pool()).acquire() as conn:
        stored = await conn.fetchval("SELECT token_hash FROM password_reset_tokens WHERE user_id = $1", user_id)
    assert stored != reset and len(stored) == 64       # only the SHA-256 is stored
    r = await client.post("/auth/reset-password", json={"token": reset, "new_password": "another good password"})
    assert r.status_code == 204
    assert (await _refresh(client, raw)).status_code == 401


async def test_non_access_tokens_are_rejected(client):
    pending = create_access_token({"type": "oauth_pending", "email": "x@example.test"}, timedelta(minutes=5))
    r = await client.get("/auth/me", headers={"Authorization": f"Bearer {pending}"})
    assert r.status_code == 401
    legacy = create_access_token({"sub": str(uuid.uuid4()), "company_id": str(uuid.uuid4())})
    r = await client.get("/auth/me", headers={"Authorization": f"Bearer {legacy}"})
    assert r.status_code == 401
