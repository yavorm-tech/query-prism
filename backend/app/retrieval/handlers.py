"""Retrieval reactions to other contexts' events (subscribed in app.bootstrap)."""
from app.knowledge.api import DocumentDeleted, DocumentIngested
from app.workspace.api import TopicDeleted
from app.retrieval.cache import invalidate_company_cache, invalidate_team_cache


async def drop_answers_for_document(event: DocumentIngested | DocumentDeleted) -> None:
    """Cached answers were computed without (or with) this document; drop every answer that could see it."""
    if event.visibility == "company":
        await invalidate_company_cache(event.company_id)
    else:
        await invalidate_team_cache(event.team_id)


async def drop_answers_for_topic(event: TopicDeleted) -> None:
    await invalidate_team_cache(event.team_id)
