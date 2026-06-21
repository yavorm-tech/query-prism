"""
Entity extractor using GPT-4o-mini — language-agnostic, works on any script.
"""
import asyncio
import json
import logging
from dataclasses import dataclass, field

from openai import AsyncOpenAI
from app.config import get_settings

logger = logging.getLogger(__name__)

VALID_TYPES = {"Person", "Organisation", "Location", "Product", "Event", "Work", "Law", "Date", "Money", "Group"}

SYSTEM_PROMPT = """You are a named entity recognition system.
Extract named entities from the given text.

Return ONLY a JSON array of objects with keys:
  text        - the entity as it appears in the text
  type        - one of: Person, Organisation, Location, Product, Event, Work, Law, Date, Money, Group
  start_char  - character offset where the entity starts (integer)
  end_char    - character offset where the entity ends (integer)

Rules:
- Include only clearly identifiable named entities
- Skip generic words, pronouns, and common nouns
- Deduplicate: if the same entity appears multiple times, include only the first occurrence
- Works on any language — do not skip non-English text
- Return [] if no named entities are found
- Return ONLY the JSON array, no other text"""

_client: AsyncOpenAI | None = None


def _get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        _client = AsyncOpenAI(api_key=get_settings().openai_api_key)
    return _client


@dataclass
class Entity:
    text: str
    normalized: str
    type: str
    start_char: int
    end_char: int
    confidence: float = 1.0


@dataclass
class ChunkEntities:
    chunk_id: str
    entities: list[Entity] = field(default_factory=list)


async def extract_entities(chunk_id: str, text: str, max_retries: int = 3) -> ChunkEntities:
    """Extract named entities from a single chunk using GPT-4o-mini."""
    client = _get_client()
    for attempt in range(max_retries):
        try:
            response = await client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": text[:3000]},
                ],
                temperature=0,
                max_tokens=1000,
            )

            raw = (response.choices[0].message.content or "[]").strip()
            if raw.startswith("```"):
                raw = raw.split("\n", 1)[-1].rsplit("```", 1)[0]

            items = json.loads(raw)
            if isinstance(items, dict):
                items = items.get("entities", [])

            entities = []
            seen: set[tuple[str, str]] = set()
            for item in items:
                etype = item.get("type", "")
                if etype not in VALID_TYPES:
                    continue
                raw_text = str(item.get("text", "")).strip()
                normalized = raw_text.lower()
                if len(normalized) < 2:
                    continue
                key = (normalized, etype)
                if key in seen:
                    continue
                seen.add(key)
                entities.append(Entity(
                    text=raw_text,
                    normalized=normalized,
                    type=etype,
                    start_char=int(item.get("start_char", 0)),
                    end_char=int(item.get("end_char", 0)),
                ))
            return ChunkEntities(chunk_id=chunk_id, entities=entities)

        except Exception as e:
            if attempt == max_retries - 1:
                logger.warning(f"[{chunk_id}] NER extraction failed: {e}")
                return ChunkEntities(chunk_id=chunk_id)
            await asyncio.sleep(2 ** attempt)

    return ChunkEntities(chunk_id=chunk_id)


async def extract_entities_batch(
    chunks: list[tuple[str, str]],
    concurrency: int = 5,
) -> list[ChunkEntities]:
    """Batch extract entities from multiple (chunk_id, text) pairs concurrently."""
    semaphore = asyncio.Semaphore(concurrency)

    async def bounded(chunk_id: str, text: str) -> ChunkEntities:
        async with semaphore:
            return await extract_entities(chunk_id, text)

    return list(await asyncio.gather(*[bounded(cid, text) for cid, text in chunks]))
