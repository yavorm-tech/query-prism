"""Slim read-only user/team helpers for the ingestion service."""
from app.db.connection import get_pool


async def get_team(team_id: str, company_id: str) -> dict | None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT id, name, company_id FROM teams WHERE id = $1 AND company_id = $2",
            team_id, company_id,
        )
    return dict(row) if row else None


async def is_team_member(team_id: str, user_id: str) -> bool:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT 1 FROM team_members WHERE team_id = $1 AND user_id = $2",
            team_id, user_id,
        )
    return row is not None
