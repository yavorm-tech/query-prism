import json
import logging
from fastapi import APIRouter, HTTPException, Depends, Request, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from app.services.retriever import retrieve
from app.services.llm import generate_answer, stream_answer, get_company_model
from app.services.auth import get_current_user, can_access_team
from app.services.rate_limit import limiter
from app.services.cache import get_cached, set_cached
from app.services.billing_client import check_query_limit, increment_query_count
from app.db.connection import get_pool
from app.services.audit import log_event

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/chat", tags=["chat"])


class ChatRequest(BaseModel):
    query: str
    team_id: str | None = None
    source_type: str | None = None
    skip_cache: bool = False


class SourceChunk(BaseModel):
    chunk_id: str
    document_id: str
    filename: str
    original_name: str
    source_type: str
    team_id: str | None = None
    content_preview: str
    similarity: float | None = None
    rerank_score: float | None = None


class ChatResponse(BaseModel):
    answer: str
    sources: list[SourceChunk]
    query: str
    cached: bool = False
    scope: str = "all"


def _format_sources(raw_sources: list[dict]) -> list[SourceChunk]:
    return [
        SourceChunk(
            chunk_id=str(s.get("chunk_id") or s.get("id", "")),
            document_id=str(s.get("document_id", "")),
            filename=s.get("filename", ""),
            original_name=s.get("original_name", ""),
            source_type=s.get("source_type", ""),
            team_id=str(s["team_id"]) if s.get("team_id") else None,
            content_preview=s.get("content_preview") or s.get("content", "")[:200],
            similarity=s.get("similarity"),
            rerank_score=s.get("rerank_score"),
        )
        for s in raw_sources
    ]


def _sources_to_cache(raw_sources: list[dict]) -> list[dict]:
    return [
        {
            "chunk_id":        str(s.get("id", s.get("chunk_id", ""))),
            "document_id":     str(s.get("document_id", "")),
            "filename":        s.get("filename", ""),
            "original_name":   s.get("original_name", ""),
            "source_type":     s.get("source_type", ""),
            "team_id":         str(s["team_id"]) if s.get("team_id") else None,
            "content_preview": s.get("content", s.get("content_preview", ""))[:200],
            "similarity":      s.get("similarity"),
            "rerank_score":    s.get("rerank_score"),
        }
        for s in raw_sources
    ]


def _no_docs_message(user: dict, team_id: str | None) -> str:
    if not user.get("team_ids"):
        return "You are not a member of any team. Ask your admin to add you to a team and upload some documents."
    if team_id:
        return "No documents found in this team. Try uploading some documents first."
    return "No documents found across your teams. Try uploading some documents first."


@router.post("", response_model=ChatResponse)
@limiter.limit("30/minute")
async def chat(request: Request, body: ChatRequest, current_user: dict = Depends(get_current_user)):
    if not body.query.strip():
        raise HTTPException(400, "Query cannot be empty")
    if body.team_id and not can_access_team(current_user, body.team_id):
        raise HTTPException(403, "You do not have access to this team")

    await check_query_limit(current_user["company_id"])
    model = await get_company_model(current_user["company_id"])

    if not body.skip_cache:
        cached = await get_cached(current_user, body.query, body.team_id)
        if cached:
            return ChatResponse(
                answer=cached["answer"], sources=_format_sources(cached["sources"]),
                query=body.query, cached=True,
            )

    context, sources = await retrieve(query=body.query, user=current_user, team_id=body.team_id, source_type=body.source_type)
    if not context:
        return ChatResponse(answer=_no_docs_message(current_user, body.team_id), sources=[], query=body.query)

    answer = await generate_answer(body.query, context, sources, model=model)
    await increment_query_count(current_user["company_id"])
    await _save_question(current_user, body.query, body.team_id, None, answer)

    serialized = _sources_to_cache(sources)
    await set_cached(current_user, body.query, answer, serialized, body.team_id)
    return ChatResponse(answer=answer, sources=_format_sources(sources), query=body.query)


@router.get("/stream")
@limiter.limit("30/minute")
async def chat_stream(
    request: Request,
    query: str,
    team_id: str | None = Query(None),
    topic_id: str | None = Query(None),
    source_type: str | None = Query(None),
    skip_cache: bool = Query(False),
    current_user: dict = Depends(get_current_user),
):
    if not query.strip():
        raise HTTPException(400, "Query cannot be empty")
    if team_id and not can_access_team(current_user, team_id):
        raise HTTPException(403, "You do not have access to this team")

    await check_query_limit(current_user["company_id"])
    model = await get_company_model(current_user["company_id"])
    company_id = current_user["company_id"]

    async def event_generator():
        try:
            if not skip_cache:
                cached = await get_cached(current_user, query, team_id)
                if cached:
                    words = cached["answer"].split(" ")
                    for i, word in enumerate(words):
                        token = word if i == len(words) - 1 else word + " "
                        yield _sse({"type": "token", "content": token, "cached": True})
                    yield _sse({"type": "sources", "content": cached["sources"], "cached": True})
                    yield _sse({"type": "done", "cached": True})
                    return

            context, sources = await retrieve(
                query=query, user=current_user, team_id=team_id, topic_id=topic_id, source_type=source_type,
            )
            if not context:
                yield _sse({"type": "token", "content": _no_docs_message(current_user, team_id)})
                yield _sse({"type": "sources", "content": []})
                yield _sse({"type": "done"})
                return

            full_answer = ""
            async for token in stream_answer(query, context, sources, model=model):
                full_answer += token
                yield _sse({"type": "token", "content": token})

            await increment_query_count(company_id)
            await _save_question(current_user, query, team_id, topic_id, full_answer)

            topic_name: str | None = None
            if topic_id:
                pool = await get_pool()
                async with pool.acquire() as conn:
                    row = await conn.fetchrow("SELECT name FROM topics WHERE id = $1", topic_id)
                    if row:
                        topic_name = row["name"]

            await log_event(
                company_id=company_id,
                event_type="question.asked",
                actor_id=current_user["sub"],
                actor_username=current_user["username"],
                team_id=team_id,
                resource_type="topic" if topic_id else "team",
                resource_id=topic_id or team_id,
                resource_name=topic_name,
                metadata={"question": query[:500]},
            )

            serialized = _sources_to_cache(sources)
            await set_cached(current_user, query, full_answer, serialized, team_id)
            yield _sse({"type": "sources", "content": serialized})
            yield _sse({"type": "done"})

        except Exception as e:
            logger.error(f"Stream error: {e}", exc_info=True)
            yield _sse({"type": "error", "content": str(e)})

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


def _sse(data: dict) -> str:
    return f"data: {json.dumps(data)}\n\n"


async def _save_question(
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
