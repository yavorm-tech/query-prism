"""
Workspace context: topics — how a team organises its knowledge.

Public API for other contexts. Everything else in this package is internal.
"""
from dataclasses import dataclass
from fastapi import HTTPException
from app.shared.security import can_access_team
from app.workspace import service


@dataclass(frozen=True)
class TopicDeleted:
    topic_id: str
    team_id: str
    company_id: str


async def get_topic(topic_id: str) -> dict | None:
    return await service.get_topic(topic_id)


async def require_topic_access(topic_id: str, user: dict) -> dict:
    """Load a topic the user may see, else 404/403. Pins admins to their own company."""
    topic = await service.get_topic(topic_id)
    if not topic or str(topic["company_id"]) != user["company_id"]:
        raise HTTPException(404, "Topic not found")
    if not can_access_team(user, str(topic["team_id"])):
        raise HTTPException(403, "Access denied")
    return topic
