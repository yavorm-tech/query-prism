"""
Relationship extractor — uses GPT-4o-mini to find (subject, relation, object) triples.
Only called on chunks that have 2+ entities — keeps API costs low.
"""
import json
import logging
import asyncio
from dataclasses import dataclass
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


@dataclass
class Relation:
    subject: str
    predicate: str
    obj: str
    confidence: float = 1.0


SYSTEM_PROMPT = """You are a knowledge graph extractor.
Given a text passage and a list of named entities found in it,
extract relationships between those entities.

Return ONLY a JSON array of objects with keys:
  subject   - the source entity (use exact name from the entity list)
  predicate - a short snake_case relationship label (e.g. works_at, located_in, part_of, founded_by)
  object    - the target entity (use exact name from the entity list)

Rules:
- Only extract relationships between entities in the provided list
- Use concise, consistent predicate names
- Return [] if no clear relationships exist
- Return ONLY the JSON array, no other text"""


async def extract_relations(
    chunk_id: str,
    text: str,
    entity_names: list[str],
    max_retries: int = 3,
) -> list[Relation]:
    if len(entity_names) < 2:
        return []

    client = get_client()
    user_msg = f"Entities: {', '.join(entity_names)}\n\nText:\n{text[:1500]}"

    for attempt in range(max_retries):
        try:
            response = await client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user",   "content": user_msg},
                ],
                temperature=0,
                max_tokens=500,
            )

            raw = response.choices[0].message.content or "[]"

            # Strip markdown code fences if present
            raw = raw.strip()
            if raw.startswith("```"):
                raw = raw.split("\n", 1)[-1]
                raw = raw.rsplit("```", 1)[0]

            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                items = parsed.get("relations", parsed.get("data", []))
            else:
                items = parsed

            relations = []
            for item in items:
                if all(k in item for k in ("subject", "predicate", "object")):
                    relations.append(Relation(
                        subject=item["subject"].strip().lower(),
                        predicate=item["predicate"].strip().lower(),
                        obj=item["object"].strip().lower(),
                    ))
            return relations

        except Exception as e:
            if attempt == max_retries - 1:
                logger.warning(f"[{chunk_id}] Relation extraction failed: {e}")
                return []
            await asyncio.sleep(2 ** attempt)

    return []


async def extract_relations_batch(
    items: list[tuple[str, str, list[str]]],
    concurrency: int = 5,
) -> dict[str, list[Relation]]:
    """Extract relations from multiple chunks concurrently."""
    semaphore = asyncio.Semaphore(concurrency)

    async def bounded(chunk_id, text, entity_names):
        async with semaphore:
            relations = await extract_relations(chunk_id, text, entity_names)
            return chunk_id, relations

    tasks = [bounded(cid, text, ents) for cid, text, ents in items]
    results = await asyncio.gather(*tasks)
    return {cid: rels for cid, rels in results}
