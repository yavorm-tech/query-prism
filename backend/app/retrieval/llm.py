"""Answer generation. The tier per company comes from metering (reserve_query);
which provider and model serve a tier is decided by app.shared.ai.llm."""
from typing import AsyncGenerator

from app.shared.ai import llm
from app.shared.ai.llm import AnswerTier

DEFAULT_TIER = AnswerTier.PREMIUM

SYSTEM_PROMPT = """You are a helpful assistant that answers questions based on the provided context.

Rules:
- Answer based ONLY on the context provided
- If the context doesn't contain enough information, say so clearly
- Be concise and direct
- When relevant, mention which document the information comes from
- Do not make up information not present in the context"""


def _user_message(query: str, context: str, sources: list[dict]) -> str:
    docs = {chunk.get("original_name") or chunk.get("filename", "Unknown") for chunk in sources}
    return f"Context (from {len(docs)} document(s)):\n{context}\n\nQuestion: {query}"


async def generate_answer(query: str, context: str, sources: list[dict], tier: str = DEFAULT_TIER) -> str:
    return await llm.complete(tier, SYSTEM_PROMPT, _user_message(query, context, sources))


async def stream_answer(query: str, context: str, sources: list[dict], tier: str = DEFAULT_TIER) -> AsyncGenerator[str, None]:
    async for text in llm.stream(tier, SYSTEM_PROMPT, _user_message(query, context, sources)):
        yield text
