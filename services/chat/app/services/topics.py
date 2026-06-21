"""
Topics repository — database operations for topic management.
"""
import logging
from app.db.connection import get_pool

logger = logging.getLogger(__name__)


async def create_topic(
    team_id: str,
    company_id: str,
    name: str,
    created_by: str,
    description: str | None = None,
) -> dict:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO topics (team_id, company_id, name, description, created_by)
            VALUES ($1, $2, $3, $4, $5)
            RETURNING id, team_id, company_id, name, description, created_by, created_at
            """,
            team_id, company_id, name, description, created_by,
        )
    return dict(row)


async def get_topics_for_team(team_id: str) -> list[dict]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT
                t.id, t.name, t.description, t.team_id, t.created_at,
                u.username AS created_by_username,
                COUNT(d.id) AS document_count,
                COUNT(d.id) FILTER (WHERE d.status = 'completed') AS completed_count
            FROM topics t
            LEFT JOIN users u ON u.id = t.created_by
            LEFT JOIN documents d ON d.topic_id = t.id
            WHERE t.team_id = $1
            GROUP BY t.id, u.username
            ORDER BY t.created_at DESC
            """,
            team_id,
        )
    return [dict(r) for r in rows]


async def get_topics_for_user(team_ids: list[str]) -> list[dict]:
    """Get all topics visible to a user across all their teams."""
    if not team_ids:
        return []
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT
                t.id, t.name, t.description, t.team_id, t.created_at,
                tm.name AS team_name,
                u.username AS created_by_username,
                COUNT(d.id) AS document_count,
                COUNT(d.id) FILTER (WHERE d.status = 'completed') AS completed_count
            FROM topics t
            LEFT JOIN teams tm ON tm.id = t.team_id
            LEFT JOIN users u ON u.id = t.created_by
            LEFT JOIN documents d ON d.topic_id = t.id
            WHERE t.team_id = ANY($1::uuid[])
            GROUP BY t.id, tm.name, u.username
            ORDER BY t.created_at DESC
            """,
            team_ids,
        )
    return [dict(r) for r in rows]


async def get_topic(topic_id: str) -> dict | None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT t.id, t.name, t.description, t.team_id, t.company_id,
                   t.created_by, t.created_at,
                   u.username AS created_by_username,
                   COUNT(d.id) AS document_count
            FROM topics t
            LEFT JOIN users u ON u.id = t.created_by
            LEFT JOIN documents d ON d.topic_id = t.id
            WHERE t.id = $1
            GROUP BY t.id, u.username
            """,
            topic_id,
        )
    return dict(row) if row else None


async def delete_topic(topic_id: str) -> bool:
    """
    Delete a topic and all its documents (CASCADE handles chunks too).
    Returns True if deleted, False if not found.
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        result = await conn.execute(
            "DELETE FROM topics WHERE id = $1",
            topic_id,
        )
    return result != "DELETE 0"


async def update_topic(
    topic_id: str,
    name: str | None = None,
    description: str | None = None,
) -> dict | None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            UPDATE topics
            SET name        = COALESCE($2, name),
                description = COALESCE($3, description),
                updated_at  = now()
            WHERE id = $1
            RETURNING id, name, description, team_id, created_at
            """,
            topic_id, name, description,
        )
    return dict(row) if row else None


async def get_topic_document_count(topic_id: str) -> int:
    pool = await get_pool()
    async with pool.acquire() as conn:
        count = await conn.fetchval(
            "SELECT COUNT(*) FROM documents WHERE topic_id = $1",
            topic_id,
        )
    return count or 0
