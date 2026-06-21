"""
Embedding service — batches chunks and calls OpenAI embeddings API.
Handles rate limiting with exponential backoff.
"""
import asyncio
import logging
from openai import AsyncOpenAI
from app.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)

_client: AsyncOpenAI | None = None


def get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        _client = AsyncOpenAI(api_key=settings.openai_api_key)
    return _client


async def embed_texts(texts: list[str]) -> list[list[float]]:
    """
    Embed a list of texts. Automatically batches into groups of
    embedding_batch_size and retries on rate limit errors.
    """
    if not texts:
        return []

    client = get_client()
    all_embeddings: list[list[float]] = []
    batch_size = settings.embedding_batch_size

    for i in range(0, len(texts), batch_size):
        batch = texts[i: i + batch_size]
        embeddings = await _embed_batch_with_retry(client, batch)
        all_embeddings.extend(embeddings)
        logger.debug(f"Embedded batch {i // batch_size + 1} / {len(texts) // batch_size + 1}")

    return all_embeddings


async def _embed_batch_with_retry(
    client: AsyncOpenAI,
    texts: list[str],
    max_retries: int = 5,
) -> list[list[float]]:
    """Single batch with exponential backoff on rate limit / server errors."""
    for attempt in range(max_retries):
        try:
            response = await client.embeddings.create(
                input=texts,
                model=settings.embedding_model,
            )
            # Sort by index to preserve order
            sorted_data = sorted(response.data, key=lambda x: x.index)
            return [item.embedding for item in sorted_data]

        except Exception as e:
            if attempt == max_retries - 1:
                raise
            wait = 2 ** attempt  # 1s, 2s, 4s, 8s, 16s
            logger.warning(f"Embedding attempt {attempt + 1} failed: {e}. Retrying in {wait}s...")
            await asyncio.sleep(wait)

    return []  # unreachable
