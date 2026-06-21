import logging
from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel
from app.services.auth import get_current_user
from app.db.connection import get_pool

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/audit", tags=["audit"])


class AuditLogItem(BaseModel):
    id: str
    event_type: str
    actor_username: str | None = None
    actor_email: str | None = None
    team_id: str | None = None
    team_name: str | None = None
    resource_type: str | None = None
    resource_id: str | None = None
    resource_name: str | None = None
    metadata: dict | None = None
    created_at: str


@router.get("", response_model=list[AuditLogItem])
async def get_audit_log(
    team_id: str | None = Query(None),
    event_type: str | None = Query(None),
    limit: int = Query(100, le=500),
    offset: int = Query(0, ge=0),
    current_user: dict = Depends(get_current_user),
):
    role = current_user.get("role")
    if role not in ("owner", "admin"):
        raise HTTPException(403, "Only company owners and admins can view audit logs")

    company_id = current_user["company_id"]
    user_team_ids = current_user.get("team_ids", [])

    pool = await get_pool()
    async with pool.acquire() as conn:

        # Admins are scoped to their teams; owners see everything
        if role == "admin" and not team_id:
            rows = await conn.fetch(
                """
                SELECT al.id, al.event_type, al.actor_username, al.actor_email,
                       al.team_id, t.name AS team_name,
                       al.resource_type, al.resource_id, al.resource_name,
                       al.metadata, al.created_at
                FROM audit_log al
                LEFT JOIN teams t ON t.id = al.team_id
                WHERE al.company_id = $1
                  AND (al.team_id = ANY($2) OR al.team_id IS NULL)
                  AND ($3::text IS NULL OR al.event_type = $3)
                ORDER BY al.created_at DESC
                LIMIT $4 OFFSET $5
                """,
                company_id, user_team_ids, event_type, limit, offset,
            )
        else:
            # Owner sees all; or specific team_id requested
            effective_team = team_id
            if role == "admin" and team_id and team_id not in user_team_ids:
                raise HTTPException(403, "Access denied to this team's audit log")

            rows = await conn.fetch(
                """
                SELECT al.id, al.event_type, al.actor_username, al.actor_email,
                       al.team_id, t.name AS team_name,
                       al.resource_type, al.resource_id, al.resource_name,
                       al.metadata, al.created_at
                FROM audit_log al
                LEFT JOIN teams t ON t.id = al.team_id
                WHERE al.company_id = $1
                  AND ($2::uuid IS NULL OR al.team_id = $2::uuid)
                  AND ($3::text IS NULL OR al.event_type = $3)
                ORDER BY al.created_at DESC
                LIMIT $4 OFFSET $5
                """,
                company_id, effective_team, event_type, limit, offset,
            )

    import json
    return [
        AuditLogItem(
            id=str(r["id"]),
            event_type=r["event_type"],
            actor_username=r["actor_username"],
            actor_email=r["actor_email"],
            team_id=str(r["team_id"]) if r["team_id"] else None,
            team_name=r["team_name"],
            resource_type=r["resource_type"],
            resource_id=r["resource_id"],
            resource_name=r["resource_name"],
            metadata=json.loads(r["metadata"]) if r["metadata"] else None,
            created_at=str(r["created_at"]),
        )
        for r in rows
    ]
