"""
User + company repository.
All database operations for auth, company, team and member management.
"""
import logging
import re
import secrets
import bcrypt
from datetime import datetime, timezone, timedelta
from app.db.connection import get_pool

logger = logging.getLogger(__name__)


# ── Password ──────────────────────────────────────────────────────────────────

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


# ── Slug ──────────────────────────────────────────────────────────────────────

def slugify(name: str) -> str:
    slug = re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-')
    return slug[:50]


async def unique_slug(base: str) -> str:
    """Generate a unique company slug — append random suffix if taken."""
    pool = await get_pool()
    slug = slugify(base)
    async with pool.acquire() as conn:
        for _ in range(5):
            existing = await conn.fetchval(
                "SELECT id FROM companies WHERE slug = $1", slug
            )
            if not existing:
                return slug
            slug = f"{slugify(base)}-{secrets.token_hex(3)}"
    return f"{slugify(base)}-{secrets.token_hex(4)}"


# ── Company ───────────────────────────────────────────────────────────────────

async def create_company(name: str) -> dict:
    pool = await get_pool()
    slug = await unique_slug(name)
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO companies (name, slug)
            VALUES ($1, $2)
            RETURNING id, name, slug, plan, created_at
            """,
            name, slug,
        )
    return dict(row)


async def get_company(company_id: str) -> dict | None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT id, name, slug, plan, max_users, max_teams FROM companies WHERE id = $1",
            company_id,
        )
    return dict(row) if row else None


# ── Teams ─────────────────────────────────────────────────────────────────────

async def create_team(company_id: str, name: str, description: str | None = None) -> dict:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO teams (company_id, name, description)
            VALUES ($1, $2, $3)
            RETURNING id, company_id, name, description, created_at
            """,
            company_id, name, description,
        )
    return dict(row)


async def get_teams_for_company(company_id: str) -> list[dict]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT t.id, t.name, t.description, t.created_at,
                   COUNT(tm.user_id) AS member_count
            FROM teams t
            LEFT JOIN team_members tm ON tm.team_id = t.id
            WHERE t.company_id = $1
            GROUP BY t.id
            ORDER BY t.created_at
            """,
            company_id,
        )
    return [dict(r) for r in rows]


async def get_team(team_id: str, company_id: str) -> dict | None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT id, name, description, company_id FROM teams WHERE id = $1 AND company_id = $2",
            team_id, company_id,
        )
    return dict(row) if row else None


async def get_user_team_ids(user_id: str) -> list[str]:
    """Return all team IDs the user belongs to."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT team_id FROM team_members WHERE user_id = $1",
            user_id,
        )
    return [str(r["team_id"]) for r in rows]


# ── Users ─────────────────────────────────────────────────────────────────────

async def create_user(
    company_id: str,
    username: str,
    email: str,
    password: str,
    role: str = "member",
) -> dict:
    pool = await get_pool()
    hashed = hash_password(password)
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO users (company_id, username, email, password, role)
            VALUES ($1, $2, $3, $4, $5)
            RETURNING id, company_id, username, email, role, created_at
            """,
            company_id, username, email, hashed, role,
        )
    return dict(row)


async def create_oauth_user(
    company_id: str,
    username: str,
    email: str,
    google_id: str,
    role: str = "member",
) -> dict:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO users (company_id, username, email, google_id, role)
            VALUES ($1, $2, $3, $4, $5)
            RETURNING id, company_id, username, email, role, created_at
            """,
            company_id, username, email, google_id, role,
        )
    return dict(row)


async def get_user_by_google_id(google_id: str) -> dict | None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT id, company_id, username, email, role,
                   default_team_id, is_active
            FROM users WHERE google_id = $1
            """,
            google_id,
        )
    return dict(row) if row else None


async def link_google_account(user_id: str, google_id: str) -> None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE users SET google_id = $1 WHERE id = $2",
            google_id, user_id,
        )


async def get_user_by_email(email: str) -> dict | None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT id, company_id, username, email, password, role,
                   default_team_id, is_active
            FROM users WHERE email = $1
            """,
            email,
        )
    return dict(row) if row else None


async def get_user_by_id(user_id: str) -> dict | None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT id, company_id, username, email, role,
                   default_team_id, is_active
            FROM users WHERE id = $1
            """,
            user_id,
        )
    return dict(row) if row else None


async def authenticate_user(email: str, password: str) -> dict | None:
    user = await get_user_by_email(email)
    if not user:
        return None
    if not user.get("is_active"):
        return None
    if not verify_password(password, user["password"]):
        return None
    return user


async def set_default_team(user_id: str, team_id: str) -> None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE users SET default_team_id = $1 WHERE id = $2",
            team_id, user_id,
        )


# ── Team membership ───────────────────────────────────────────────────────────

async def add_team_member(team_id: str, user_id: str, role: str = "member") -> None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO team_members (team_id, user_id, role)
            VALUES ($1, $2, $3)
            ON CONFLICT (team_id, user_id) DO UPDATE SET role = $3
            """,
            team_id, user_id, role,
        )


async def remove_team_member(team_id: str, user_id: str) -> bool:
    pool = await get_pool()
    async with pool.acquire() as conn:
        result = await conn.execute(
            "DELETE FROM team_members WHERE team_id = $1 AND user_id = $2",
            team_id, user_id,
        )
    return result != "DELETE 0"


async def get_team_members(team_id: str) -> list[dict]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT u.id, u.username, u.email, u.role AS company_role,
                   tm.role AS team_role, tm.joined_at
            FROM team_members tm
            JOIN users u ON u.id = tm.user_id
            WHERE tm.team_id = $1
            ORDER BY tm.joined_at
            """,
            team_id,
        )
    return [dict(r) for r in rows]


async def is_team_member(team_id: str, user_id: str) -> bool:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT 1 FROM team_members WHERE team_id = $1 AND user_id = $2",
            team_id, user_id,
        )
    return row is not None


# ── Invites ───────────────────────────────────────────────────────────────────

async def list_invites_for_company(company_id: str) -> list[dict]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT i.id, i.email, i.role, i.token,
                   i.accepted_at, i.expires_at, i.created_at,
                   t.name AS team_name,
                   u.username AS invited_by_username
            FROM invites i
            JOIN teams t ON t.id = i.team_id
            JOIN users u ON u.id = i.invited_by
            WHERE i.company_id = $1
            ORDER BY i.created_at DESC
            """,
            company_id,
        )
    return [dict(r) for r in rows]


async def create_invite(
    company_id: str,
    team_id: str,
    email: str,
    invited_by: str,
    role: str = "member",
    expires_hours: int = 24,
) -> dict:
    pool = await get_pool()
    token = secrets.token_urlsafe(32)
    expires_at = datetime.now(timezone.utc) + timedelta(hours=expires_hours)
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO invites (company_id, team_id, email, role, token, invited_by, expires_at)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            RETURNING id, token, email, expires_at
            """,
            company_id, team_id, email, role, token, invited_by, expires_at,
        )
    return dict(row)


async def get_invite_by_token(token: str) -> dict | None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT i.*, c.name AS company_name, t.name AS team_name
            FROM invites i
            JOIN companies c ON c.id = i.company_id
            JOIN teams t ON t.id = i.team_id
            WHERE i.token = $1
              AND i.accepted_at IS NULL
              AND i.expires_at > now()
            """,
            token,
        )
    return dict(row) if row else None


async def accept_invite(token: str) -> None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE invites SET accepted_at = now() WHERE token = $1",
            token,
        )


async def create_password_reset_token(user_id: str) -> str:
    import secrets
    from datetime import datetime, timedelta, timezone
    token = secrets.token_urlsafe(32)
    expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
    pool = await get_pool()
    async with pool.acquire() as conn:
        # Invalidate any existing unused tokens for this user
        await conn.execute(
            "UPDATE password_reset_tokens SET used_at = now() WHERE user_id = $1 AND used_at IS NULL",
            user_id,
        )
        await conn.execute(
            """
            INSERT INTO password_reset_tokens (user_id, token, expires_at)
            VALUES ($1, $2, $3)
            """,
            user_id, token, expires_at,
        )
    return token


async def get_reset_token(token: str) -> dict | None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT r.*, u.email, u.id AS uid
            FROM password_reset_tokens r
            JOIN users u ON u.id = r.user_id
            WHERE r.token = $1
              AND r.used_at IS NULL
              AND r.expires_at > now()
            """,
            token,
        )
    return dict(row) if row else None


async def consume_reset_token(token: str, new_password: str) -> bool:
    hashed = hash_password(new_password)
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            UPDATE password_reset_tokens SET used_at = now()
            WHERE token = $1 AND used_at IS NULL AND expires_at > now()
            RETURNING user_id
            """,
            token,
        )
        if not row:
            return False
        await conn.execute(
            "UPDATE users SET password = $1 WHERE id = $2",
            hashed, str(row["user_id"]),
        )
    return True


# ── Avatar ────────────────────────────────────────────────────────────────────

async def update_user_avatar(user_id: str, avatar: str | None) -> None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE users SET avatar = $2 WHERE id = $1",
            user_id, avatar,
        )


async def get_user_avatar(user_id: str) -> str | None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetchval("SELECT avatar FROM users WHERE id = $1", user_id)
