"""
Usage tracking service — enforces per-plan limits and tracks consumption.

All limit checks raise HTTP exceptions before the action is allowed.
All increment/decrement operations use atomic SQL to avoid race conditions.
"""
import logging
from fastapi import HTTPException
from app.db.connection import get_pool

logger = logging.getLogger(__name__)


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _get_company_with_plan(company_id: str) -> dict | None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT c.plan,
                   c.queries_used_this_month,
                   c.queries_reset_at,
                   c.storage_used_bytes,
                   pl.max_queries,
                   pl.max_storage_mb,
                   pl.max_teams,
                   pl.max_users,
                   pl.llm_model
            FROM companies c
            JOIN plan_limits pl ON pl.plan = c.plan
            WHERE c.id = $1
            """,
            company_id,
        )
    return dict(row) if row else None


async def _reset_if_new_month(company_id: str) -> None:
    """Atomically reset the monthly query counter if the billing period has rolled over."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE companies SET
                queries_used_this_month = 0,
                queries_reset_at = date_trunc('month', now())
            WHERE id = $1
              AND date_trunc('month', now()) > date_trunc('month', queries_reset_at)
            """,
            company_id,
        )


# ── Limit checks ──────────────────────────────────────────────────────────────

async def check_query_limit(company_id: str) -> None:
    await _reset_if_new_month(company_id)

    row = await _get_company_with_plan(company_id)
    if not row:
        return

    if row["max_queries"] is None:
        return  # unlimited

    if row["queries_used_this_month"] >= row["max_queries"]:
        raise HTTPException(
            status_code=429,
            detail={
                "error": "query_limit_reached",
                "message": f"You've used all {row['max_queries']} queries for this month.",
                "used": row["queries_used_this_month"],
                "limit": row["max_queries"],
                "plan": row["plan"],
                "upgrade_url": "/settings/billing",
            },
        )


async def check_storage_limit(company_id: str, file_size_bytes: int) -> None:
    row = await _get_company_with_plan(company_id)
    if not row:
        return

    if row["max_storage_mb"] is None:
        return  # unlimited

    max_bytes = row["max_storage_mb"] * 1024 * 1024
    if row["storage_used_bytes"] + file_size_bytes > max_bytes:
        used_mb = row["storage_used_bytes"] / (1024 * 1024)
        limit_mb = row["max_storage_mb"]
        raise HTTPException(
            status_code=413,
            detail={
                "error": "storage_limit_reached",
                "message": f"Storage limit reached ({used_mb:.1f} MB / {limit_mb} MB used).",
                "used_mb": round(used_mb, 1),
                "limit_mb": limit_mb,
                "plan": row["plan"],
                "upgrade_url": "/settings/billing",
            },
        )


async def check_team_limit(company_id: str) -> None:
    row = await _get_company_with_plan(company_id)
    if not row:
        return

    if row["max_teams"] is None:
        return  # unlimited

    pool = await get_pool()
    async with pool.acquire() as conn:
        team_count = await conn.fetchval(
            "SELECT COUNT(*) FROM teams WHERE company_id = $1", company_id
        )

    if team_count >= row["max_teams"]:
        raise HTTPException(
            status_code=403,
            detail={
                "error": "team_limit_reached",
                "message": f"Your {row['plan']} plan allows {row['max_teams']} team(s). Upgrade to create more.",
                "used": team_count,
                "limit": row["max_teams"],
                "plan": row["plan"],
                "upgrade_url": "/settings/billing",
            },
        )


async def check_user_limit(company_id: str) -> None:
    row = await _get_company_with_plan(company_id)
    if not row:
        return

    if row["max_users"] is None:
        return  # unlimited

    pool = await get_pool()
    async with pool.acquire() as conn:
        user_count = await conn.fetchval(
            "SELECT COUNT(*) FROM users WHERE company_id = $1", company_id
        )

    if user_count >= row["max_users"]:
        raise HTTPException(
            status_code=403,
            detail={
                "error": "user_limit_reached",
                "message": f"Your {row['plan']} plan allows {row['max_users']} user(s). Upgrade to add more.",
                "used": user_count,
                "limit": row["max_users"],
                "plan": row["plan"],
                "upgrade_url": "/settings/billing",
            },
        )


# ── Counters ──────────────────────────────────────────────────────────────────

async def increment_query_count(company_id: str) -> None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE companies SET queries_used_this_month = queries_used_this_month + 1 WHERE id = $1",
            company_id,
        )


async def increment_storage(company_id: str, bytes_count: int) -> None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE companies SET storage_used_bytes = storage_used_bytes + $2 WHERE id = $1",
            company_id, bytes_count,
        )


async def decrement_storage(company_id: str, bytes_count: int) -> None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE companies SET
                storage_used_bytes = GREATEST(0, storage_used_bytes - $2)
            WHERE id = $1
            """,
            company_id, bytes_count,
        )


# ── Usage summary ─────────────────────────────────────────────────────────────

async def get_usage(company_id: str) -> dict:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT
                c.plan,
                c.queries_used_this_month,
                c.queries_reset_at,
                c.storage_used_bytes,
                pl.max_queries,
                pl.max_storage_mb,
                pl.max_teams,
                pl.max_users,
                pl.price_monthly,
                (SELECT COUNT(*) FROM teams WHERE company_id = c.id)::int AS team_count,
                (SELECT COUNT(*) FROM users WHERE company_id = c.id)::int AS user_count
            FROM companies c
            JOIN plan_limits pl ON pl.plan = c.plan
            WHERE c.id = $1
            """,
            company_id,
        )

    if not row:
        raise HTTPException(404, "Company not found")

    used_queries = row["queries_used_this_month"] or 0
    max_queries  = row["max_queries"]
    used_bytes   = row["storage_used_bytes"] or 0
    max_storage_mb = row["max_storage_mb"]
    used_mb      = used_bytes / (1024 * 1024)

    return {
        "plan": row["plan"],
        "price_monthly": float(row["price_monthly"]) if row["price_monthly"] else 0.0,
        "queries": {
            "used": used_queries,
            "limit": max_queries,
            "resets_at": row["queries_reset_at"].isoformat() if row["queries_reset_at"] else None,
            "percent": round((used_queries / max_queries * 100), 1) if max_queries else 0.0,
        },
        "storage": {
            "used_bytes": used_bytes,
            "used_mb": round(used_mb, 2),
            "limit_mb": max_storage_mb,
            "percent": round((used_mb / max_storage_mb * 100), 1) if max_storage_mb else 0.0,
        },
        "teams": {
            "used": row["team_count"],
            "limit": row["max_teams"],
        },
        "users": {
            "used": row["user_count"],
            "limit": row["max_users"],
        },
    }


# ── Model lookup ──────────────────────────────────────────────────────────────

async def get_model_for_company(company_id: str) -> str:
    pool = await get_pool()
    async with pool.acquire() as conn:
        model = await conn.fetchval(
            """
            SELECT pl.llm_model
            FROM companies c
            JOIN plan_limits pl ON pl.plan = c.plan
            WHERE c.id = $1
            """,
            company_id,
        )
    return model or "claude-sonnet-4-6"
