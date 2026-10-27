"""
Usage tracking — enforces per-plan limits and tracks consumption.

Owns metering.subscriptions (plan + counters per company) and
metering.plan_limits. All increment/decrement operations use atomic SQL to
avoid race conditions. Team and user counts belong to identity, so callers
pass them in (limit checks) or they come through the TenantDirectory port
(usage report).
"""
import logging
from typing import Protocol
from fastapi import HTTPException
from app.shared.db import get_pool

logger = logging.getLogger(__name__)

DEFAULT_PLAN = "starter"
DEFAULT_MODEL = "claude-sonnet-4-6"


class TenantDirectory(Protocol):
    """Port implemented by identity; wired in app.bootstrap."""
    async def count_teams(self, company_id: str) -> int: ...
    async def count_users(self, company_id: str) -> int: ...


_directory: TenantDirectory | None = None


def set_tenant_directory(directory: TenantDirectory) -> None:
    global _directory
    _directory = directory


# ── Subscriptions ─────────────────────────────────────────────────────────────

async def open_subscription(company_id: str, plan: str = DEFAULT_PLAN) -> None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO subscriptions (company_id, plan) VALUES ($1, $2) ON CONFLICT (company_id) DO NOTHING",
            company_id, plan,
        )


async def _get_subscription(company_id: str) -> dict | None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT s.plan,
                   s.queries_used_this_month,
                   s.queries_reset_at,
                   s.storage_used_bytes,
                   pl.max_queries,
                   pl.max_storage_mb,
                   pl.max_teams,
                   pl.max_users,
                   pl.llm_model,
                   pl.price_monthly
            FROM subscriptions s
            JOIN plan_limits pl ON pl.plan = s.plan
            WHERE s.company_id = $1
            """,
            company_id,
        )
    return dict(row) if row else None


async def get_plan(company_id: str) -> str:
    row = await _get_subscription(company_id)
    return row["plan"] if row else DEFAULT_PLAN


async def _reset_if_new_month(company_id: str) -> None:
    """Atomically reset the monthly query counter if the billing period has rolled over."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE subscriptions SET
                queries_used_this_month = 0,
                queries_reset_at = date_trunc('month', now())
            WHERE company_id = $1
              AND date_trunc('month', now()) > date_trunc('month', queries_reset_at)
            """,
            company_id,
        )


# ── Limit checks ──────────────────────────────────────────────────────────────

def _query_limit_error(row: dict) -> HTTPException:
    return HTTPException(
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
    row = await _get_subscription(company_id)
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


async def check_team_limit(company_id: str, team_count: int) -> None:
    row = await _get_subscription(company_id)
    if not row or row["max_teams"] is None:
        return  # unknown company or unlimited

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


async def check_user_limit(company_id: str, user_count: int) -> None:
    row = await _get_subscription(company_id)
    if not row or row["max_users"] is None:
        return  # unknown company or unlimited

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

async def reserve_query(company_id: str, _open_if_missing: bool = True) -> str:
    """
    Consume one query in a single statement: rolls the month over if needed and
    only increments while under the plan limit, so concurrent requests can't overshoot.
    Returns the plan's LLM model; raises 429 when the quota is exhausted.
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        model = await conn.fetchval(
            """
            WITH period AS (SELECT date_trunc('month', now()) AS start)
            UPDATE subscriptions s SET
                queries_used_this_month = CASE
                    WHEN period.start > date_trunc('month', s.queries_reset_at) THEN 1
                    ELSE s.queries_used_this_month + 1
                END,
                queries_reset_at = CASE
                    WHEN period.start > date_trunc('month', s.queries_reset_at) THEN period.start
                    ELSE s.queries_reset_at
                END,
                updated_at = now()
            FROM plan_limits pl, period
            WHERE s.company_id = $1
              AND pl.plan = s.plan
              AND (
                  pl.max_queries IS NULL
                  OR period.start > date_trunc('month', s.queries_reset_at)
                  OR s.queries_used_this_month < pl.max_queries
              )
            RETURNING pl.llm_model
            """,
            company_id,
        )
    if model:
        return model

    # Nothing updated: the quota is exhausted, or the company has no subscription
    # yet (opened lazily so a missed registration hook can't block the company).
    row = await _get_subscription(company_id)
    if row is None and _open_if_missing:
        await open_subscription(company_id)
        return await reserve_query(company_id, _open_if_missing=False)
    if row is None:
        raise HTTPException(500, "No subscription for company")
    raise _query_limit_error(row)


async def release_query(company_id: str) -> None:
    """Give back a reserved query that did not lead to an LLM call."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE subscriptions
               SET queries_used_this_month = GREATEST(0, queries_used_this_month - 1), updated_at = now()
             WHERE company_id = $1
            """,
            company_id,
        )


async def increment_storage(company_id: str, bytes_count: int) -> None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE subscriptions SET storage_used_bytes = storage_used_bytes + $2, updated_at = now() WHERE company_id = $1",
            company_id, bytes_count,
        )


async def decrement_storage(company_id: str, bytes_count: int) -> None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE subscriptions SET
                storage_used_bytes = GREATEST(0, storage_used_bytes - $2),
                updated_at = now()
            WHERE company_id = $1
            """,
            company_id, bytes_count,
        )


# ── Usage summary ─────────────────────────────────────────────────────────────

async def get_usage(company_id: str) -> dict:
    await _reset_if_new_month(company_id)
    row = await _get_subscription(company_id)
    if not row:
        await open_subscription(company_id)
        row = await _get_subscription(company_id)
    if not row:
        raise HTTPException(404, "Company not found")

    team_count = await _directory.count_teams(company_id) if _directory else 0
    user_count = await _directory.count_users(company_id) if _directory else 0

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
            "used": team_count,
            "limit": row["max_teams"],
        },
        "users": {
            "used": user_count,
            "limit": row["max_users"],
        },
    }
