import json
import logging
from app.db.connection import get_pool

logger = logging.getLogger(__name__)


async def log_event(
    company_id: str,
    event_type: str,
    actor_id: str | None = None,
    actor_username: str | None = None,
    actor_email: str | None = None,
    team_id: str | None = None,
    resource_type: str | None = None,
    resource_id: str | None = None,
    resource_name: str | None = None,
    metadata: dict | None = None,
    ip_address: str | None = None,
) -> None:
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO audit_log
                    (company_id, team_id, actor_id, actor_username, actor_email,
                     event_type, resource_type, resource_id, resource_name, metadata, ip_address)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
                """,
                company_id, team_id, actor_id, actor_username, actor_email,
                event_type, resource_type, resource_id, resource_name,
                json.dumps(metadata) if metadata else None,
                ip_address,
            )
    except Exception as e:
        logger.warning(f"Failed to write audit log [{event_type}]: {e}")
