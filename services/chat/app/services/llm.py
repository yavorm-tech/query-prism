"""LLM service for chat — mirrors the monolith version but uses local DB for model lookup."""
import logging
from typing import AsyncGenerator
from app.config import get_settings
from app.db.connection import get_pool

settings = get_settings()
logger = logging.getLogger(__name__)

DEFAULT_MODEL = "claude-sonnet-4-6"

SYSTEM_PROMPT = """You are a helpful assistant that answers questions based on the provided context.

Rules:
- Answer based ONLY on the context provided
- If the context doesn't contain enough information, say so clearly
- Be concise and direct
- When relevant, mention which document the information comes from
- Do not make up information not present in the context"""


def _format_context(context: str, sources: list[dict]) -> str:
    seen = set()
    for chunk in sources:
        doc_name = chunk.get("original_name") or chunk.get("filename", "Unknown")
        seen.add(doc_name)
    return f"Context (from {len(seen)} document(s)):\n{context}"


async def generate_answer(query: str, context: str, sources: list[dict], model: str = DEFAULT_MODEL) -> str:
    if model.startswith("gpt-"):
        return await _openai_generate(query, context, sources, model)
    return await _claude_generate(query, context, sources, model)


async def stream_answer(query: str, context: str, sources: list[dict], model: str = DEFAULT_MODEL) -> AsyncGenerator[str, None]:
    if model.startswith("gpt-"):
        async for chunk in _openai_stream(query, context, sources, model):
            yield chunk
    else:
        async for chunk in _claude_stream(query, context, sources, model):
            yield chunk


async def _claude_generate(query: str, context: str, sources: list[dict], model: str) -> str:
    import anthropic
    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
    formatted = _format_context(context, sources)
    message = await client.messages.create(
        model=model, max_tokens=1024, system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": f"{formatted}\n\nQuestion: {query}"}],
    )
    return message.content[0].text


async def _claude_stream(query: str, context: str, sources: list[dict], model: str) -> AsyncGenerator[str, None]:
    import anthropic
    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
    formatted = _format_context(context, sources)
    async with client.messages.stream(
        model=model, max_tokens=1024, system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": f"{formatted}\n\nQuestion: {query}"}],
    ) as stream:
        async for text in stream.text_stream:
            yield text


async def _openai_generate(query: str, context: str, sources: list[dict], model: str) -> str:
    from openai import AsyncOpenAI
    client = AsyncOpenAI(api_key=settings.openai_api_key)
    formatted = _format_context(context, sources)
    response = await client.chat.completions.create(
        model=model, max_tokens=1024,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"{formatted}\n\nQuestion: {query}"},
        ],
    )
    return response.choices[0].message.content or ""


async def _openai_stream(query: str, context: str, sources: list[dict], model: str) -> AsyncGenerator[str, None]:
    from openai import AsyncOpenAI
    client = AsyncOpenAI(api_key=settings.openai_api_key)
    formatted = _format_context(context, sources)
    stream = await client.chat.completions.create(
        model=model, max_tokens=1024, stream=True,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"{formatted}\n\nQuestion: {query}"},
        ],
    )
    async for chunk in stream:
        delta = chunk.choices[0].delta.content
        if delta:
            yield delta


async def get_company_model(company_id: str) -> str:
    pool = await get_pool()
    async with pool.acquire() as conn:
        model = await conn.fetchval(
            """
            SELECT pl.llm_model FROM companies c
            JOIN plan_limits pl ON pl.plan = c.plan
            WHERE c.id = $1
            """,
            company_id,
        )
    return model or DEFAULT_MODEL
