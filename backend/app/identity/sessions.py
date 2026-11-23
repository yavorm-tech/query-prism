"""
Refresh-token sessions (ADR-009).

Access tokens are short-lived JWTs. A session is a chain ("family") of opaque
refresh tokens, each usable once: using one marks it used and issues the next.
Only SHA-256 hashes are stored.

Presenting a token that was already used means it was copied, so the whole
family is revoked — except within REUSE_GRACE of its first use, which is two
browser tabs refreshing at the same moment and gets a fresh token instead.
"""
import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone

from app.shared.config import get_settings
from app.shared.db import get_pool

REUSE_GRACE = timedelta(seconds=30)


def hash_token(raw: str) -> str:
    """SHA-256 of a one-time token; only this is stored (refresh and reset tokens)."""
    return hashlib.sha256(raw.encode()).hexdigest()


async def _insert(conn, user_id: str, family_id: str) -> str:
    raw = secrets.token_urlsafe(48)
    expires_at = datetime.now(timezone.utc) + timedelta(days=get_settings().refresh_token_days)
    await conn.execute(
        """
        INSERT INTO refresh_tokens (user_id, family_id, token_hash, expires_at)
        VALUES ($1, $2, $3, $4)
        """,
        user_id, family_id, hash_token(raw), expires_at,
    )
    return raw


async def start_session(user_id: str) -> str:
    """A new family for a fresh login. Returns the raw refresh token."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await _insert(conn, user_id, str(uuid.uuid4()))


async def rotate(raw: str) -> tuple[str, str] | None:
    """Exchange a refresh token for the next one. Returns (user_id, new raw token) or None."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            row = await conn.fetchrow(
                """
                SELECT id, user_id, family_id, expires_at, used_at, revoked_at
                FROM refresh_tokens WHERE token_hash = $1 FOR UPDATE
                """,
                hash_token(raw),
            )
            if not row or row["revoked_at"] is not None:
                return None
            now = datetime.now(timezone.utc)
            if row["expires_at"] <= now:
                return None
            if row["used_at"] is not None and now - row["used_at"] > REUSE_GRACE:
                await conn.execute(
                    "UPDATE refresh_tokens SET revoked_at = now() WHERE family_id = $1 AND revoked_at IS NULL",
                    row["family_id"],
                )
                return None
            if row["used_at"] is None:
                await conn.execute("UPDATE refresh_tokens SET used_at = now() WHERE id = $1", row["id"])
            user_id, family_id = str(row["user_id"]), str(row["family_id"])
            return user_id, await _insert(conn, user_id, family_id)


async def end_session(raw: str) -> None:
    """Logout: revoke the family the token belongs to."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE refresh_tokens SET revoked_at = now()
            WHERE revoked_at IS NULL
              AND family_id = (SELECT family_id FROM refresh_tokens WHERE token_hash = $1)
            """,
            hash_token(raw),
        )


async def end_all_sessions(user_id: str) -> None:
    """Revoke every session of a user (password change, deactivation)."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE refresh_tokens SET revoked_at = now() WHERE user_id = $1 AND revoked_at IS NULL",
            user_id,
        )
