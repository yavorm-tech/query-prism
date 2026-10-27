"""Question history — retrieval owns retrieval.query_history."""
import logging
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from app.shared.db import get_pool
from app.shared.security import get_current_user
from app.workspace.api import require_topic_access

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/topics", tags=["chat"])


async def save_question(
    user: dict, question: str, team_id: str | None, topic_id: str | None, answer: str = "",
) -> None:
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO query_history (company_id, team_id, topic_id, user_id, question, answer)
                VALUES ($1, $2, $3, $4, $5, $6)
                """,
                user["company_id"], team_id, topic_id, user["sub"], question, answer or None,
            )
    except Exception as e:
        logger.warning(f"Failed to save question to history: {e}")


class QuestionHistoryItem(BaseModel):
    id: str
    question: str
    answer: str | None
    username: str | None
    asked_at: str


@router.get("/{topic_id}/questions", response_model=list[QuestionHistoryItem])
async def list_topic_questions(
    topic_id: str,
    current_user: dict = Depends(get_current_user),
):
    """List questions asked within a specific topic, most recent first."""
    await require_topic_access(topic_id, current_user)

    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT qh.id, qh.question, qh.answer, qh.asked_at, u.username
            FROM query_history qh
            LEFT JOIN users u ON u.id = qh.user_id
            WHERE qh.topic_id = $1
            ORDER BY qh.asked_at DESC
            LIMIT 200
            """,
            topic_id,
        )

    return [
        QuestionHistoryItem(
            id=str(r["id"]),
            question=r["question"],
            answer=r.get("answer"),
            username=r.get("username"),
            asked_at=str(r["asked_at"]),
        )
        for r in rows
    ]
