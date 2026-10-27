"""
Topics router — folder-like organisation within teams.

Rules:
  - Any team member can create a topic
  - All team members can view topics
  - Any team member can upload to any topic
  - Only team admin or company admin/owner can delete a topic
  - Deleting a topic keeps its documents; they lose the topic link (SET NULL)

  GET    /topics                  — list topics visible to user
  GET    /topics?team_id=X        — filter by team
  POST   /topics                  — create a topic
  GET    /topics/{id}             — get topic details
  PATCH  /topics/{id}             — update name/description (creator or admin)
  DELETE /topics/{id}             — delete topic (admin only)

  GET /topics/{id}/documents is served by knowledge, /topics/{id}/questions by retrieval.
"""
import logging
from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel
from app.shared import events
from app.shared.security import get_current_user, can_access_team
from app.shared.db import get_pool
from app.workspace.service import (
    create_topic, get_topics_for_team, get_topics_for_user,
    delete_topic, update_topic,
)
from app.workspace.api import TopicDeleted, require_topic_access
from app.identity.api import get_team
from app.audit.api import log_event

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/topics", tags=["topics"])


# ── Models ────────────────────────────────────────────────────────────────────

class CreateTopicRequest(BaseModel):
    team_id: str
    name: str
    description: str | None = None


class UpdateTopicRequest(BaseModel):
    name: str | None = None
    description: str | None = None


class TopicResponse(BaseModel):
    id: str
    name: str
    description: str | None = None
    team_id: str
    team_name: str | None = None
    created_by_username: str | None = None
    document_count: int = 0
    completed_count: int = 0
    created_at: str




# ── Helpers ───────────────────────────────────────────────────────────────────

def _is_team_admin(user: dict, team_id: str) -> bool:
    """Check if user is a team admin or company admin/owner."""
    return user.get("role") in ("admin", "owner")



# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("", response_model=list[TopicResponse])
async def list_topics(
    team_id: str | None = Query(None, description="Filter by team"),
    current_user: dict = Depends(get_current_user),
):
    """List all topics visible to the current user."""
    role = current_user.get("role", "member")
    company_id = current_user["company_id"]

    if team_id:
        # Validate access to this specific team
        if not can_access_team(current_user, team_id) or not await get_team(team_id, company_id):
            raise HTTPException(403, "Access denied")
        topics = await get_topics_for_team(team_id)
    elif role in ("admin", "owner"):
        # Admins see all topics in the company
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
                WHERE t.company_id = $1
                GROUP BY t.id, tm.name, u.username
                ORDER BY t.created_at DESC
                """,
                company_id,
            )
        topics = [dict(r) for r in rows]
    else:
        # Members see topics from their teams
        team_ids = current_user.get("team_ids") or []
        topics = await get_topics_for_user(team_ids)

    return [
        TopicResponse(
            id=str(t["id"]),
            name=t["name"],
            description=t.get("description"),
            team_id=str(t["team_id"]),
            team_name=t.get("team_name"),
            created_by_username=t.get("created_by_username"),
            document_count=t.get("document_count") or 0,
            completed_count=t.get("completed_count") or 0,
            created_at=str(t["created_at"]),
        )
        for t in topics
    ]


@router.post("", response_model=TopicResponse, status_code=201)
async def create_topic_endpoint(
    request: CreateTopicRequest,
    current_user: dict = Depends(get_current_user),
):
    """Any team member can create a topic."""
    if not can_access_team(current_user, request.team_id) or not await get_team(request.team_id, current_user["company_id"]):
        raise HTTPException(403, "You are not a member of this team")

    if not request.name.strip():
        raise HTTPException(400, "Topic name cannot be empty")

    try:
        topic = await create_topic(
            team_id=request.team_id,
            company_id=current_user["company_id"],
            name=request.name.strip(),
            created_by=current_user["sub"],
            description=request.description,
        )
    except Exception as e:
        if "unique" in str(e).lower():
            raise HTTPException(409, f"A topic named '{request.name}' already exists in this team")
        raise

    await log_event(
        company_id=current_user["company_id"],
        event_type="topic.created",
        actor_id=current_user["sub"],
        actor_username=current_user["username"],
        team_id=request.team_id,
        resource_type="topic",
        resource_id=str(topic["id"]),
        resource_name=topic["name"],
    )
    logger.info(f"[{current_user['username']}] Created topic '{request.name}'")

    return TopicResponse(
        id=str(topic["id"]),
        name=topic["name"],
        description=topic.get("description"),
        team_id=str(topic["team_id"]),
        created_by_username=current_user["username"],
        document_count=0,
        completed_count=0,
        created_at=str(topic["created_at"]),
    )


@router.get("/{topic_id}", response_model=TopicResponse)
async def get_topic_endpoint(
    topic_id: str,
    current_user: dict = Depends(get_current_user),
):
    topic = await require_topic_access(topic_id, current_user)
    return TopicResponse(
        id=str(topic["id"]),
        name=topic["name"],
        description=topic.get("description"),
        team_id=str(topic["team_id"]),
        created_by_username=topic.get("created_by_username"),
        document_count=topic.get("document_count") or 0,
        completed_count=0,
        created_at=str(topic["created_at"]),
    )


@router.patch("/{topic_id}", response_model=TopicResponse)
async def update_topic_endpoint(
    topic_id: str,
    request: UpdateTopicRequest,
    current_user: dict = Depends(get_current_user),
):
    """Update topic name/description — creator or admin only."""
    topic = await require_topic_access(topic_id, current_user)

    is_creator = str(topic["created_by"]) == current_user["sub"]
    is_admin = _is_team_admin(current_user, str(topic["team_id"]))

    if not is_creator and not is_admin:
        raise HTTPException(403, "Only the topic creator or an admin can edit this topic")

    updated = await update_topic(
        topic_id=topic_id,
        name=request.name,
        description=request.description,
    )

    await log_event(
        company_id=current_user["company_id"],
        event_type="topic.updated",
        actor_id=current_user["sub"],
        actor_username=current_user["username"],
        team_id=str(updated["team_id"]),
        resource_type="topic",
        resource_id=topic_id,
        resource_name=updated["name"],
    )

    return TopicResponse(
        id=str(updated["id"]),
        name=updated["name"],
        description=updated.get("description"),
        team_id=str(updated["team_id"]),
        document_count=0,
        created_at=str(updated["created_at"]),
    )


@router.delete("/{topic_id}", status_code=204)
async def delete_topic_endpoint(
    topic_id: str,
    current_user: dict = Depends(get_current_user),
):
    """
    Delete a topic (its documents are kept, unassigned).
    Only team admin or company admin/owner can do this.
    """
    topic = await require_topic_access(topic_id, current_user)

    if not _is_team_admin(current_user, str(topic["team_id"])):
        raise HTTPException(
            403,
            "Only a team admin or company admin can delete topics"
        )

    team_id = str(topic["team_id"])
    deleted = await delete_topic(topic_id)
    if not deleted:
        raise HTTPException(404, "Topic not found")

    await events.publish(TopicDeleted(topic_id=topic_id, team_id=team_id, company_id=current_user["company_id"]))
    await log_event(
        company_id=current_user["company_id"],
        event_type="topic.deleted",
        actor_id=current_user["sub"],
        actor_username=current_user["username"],
        team_id=team_id,
        resource_type="topic",
        resource_id=topic_id,
        resource_name=topic["name"],
    )
    logger.info(f"[{current_user['username']}] Deleted topic '{topic['name']}'")

