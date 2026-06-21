"""
Answer cache — team-scoped keys.
Cache key: SHA256 of (company_id + sorted_team_ids + query).
Admins get a separate key based on company_id alone.
"""
import hashlib
import json
import logging
from typing import Any
import redis.asyncio as aioredis
from app.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)

CACHE_TTL = 60 * 60
CACHE_PREFIX = "rag:answer:"

_redis: aioredis.Redis | None = None


async def get_redis() -> aioredis.Redis:
    global _redis
    if _redis is None:
        _redis = aioredis.from_url(
            settings.redis_url,
            encoding="utf-8",
            decode_responses=True,
        )
    return _redis


async def close_redis():
    global _redis
    if _redis:
        await _redis.aclose()
        _redis = None


def _cache_key(user: dict, query: str, team_id: str | None = None) -> str:
    """
    Build a cache key scoped to what the user can see.
    Admins: keyed by company_id (they see everything)
    Members: keyed by sorted team_ids (they see their teams)
    Optional team_id scope narrows further.
    """
    normalized = query.strip().lower()
    role = user.get("role", "member")
    company_id = user.get("company_id", "")

    if role in ("admin", "owner"):
        scope = f"company:{company_id}"
    else:
        team_ids = sorted(user.get("team_ids") or [])
        scope = f"teams:{','.join(team_ids)}"

    if team_id:
        scope += f":filter:{team_id}"

    digest = hashlib.sha256(f"{scope}:{normalized}".encode()).hexdigest()
    return f"{CACHE_PREFIX}{digest}"


def _team_index_key(team_id: str) -> str:
    return f"rag:team_keys:{team_id}"


def _company_index_key(company_id: str) -> str:
    return f"rag:company_keys:{company_id}"


async def get_cached(
    user: dict,
    query: str,
    team_id: str | None = None,
) -> dict[str, Any] | None:
    try:
        r = await get_redis()
        key = _cache_key(user, query, team_id)
        raw = await r.get(key)
        if raw:
            logger.debug(f"Cache HIT [{user.get('username')}]: {query[:60]}")
            return json.loads(raw)
        logger.debug(f"Cache MISS [{user.get('username')}]: {query[:60]}")
        return None
    except Exception as e:
        logger.warning(f"Cache get failed: {e}")
        return None


async def set_cached(
    user: dict,
    query: str,
    answer: str,
    sources: list[dict],
    team_id: str | None = None,
    ttl: int = CACHE_TTL,
) -> None:
    """
    Store answer and track key in both team and company indexes
    for efficient invalidation.
    """
    try:
        r = await get_redis()
        key = _cache_key(user, query, team_id)
        payload = json.dumps({"answer": answer, "sources": sources})
        company_id = user.get("company_id", "")

        pipe = r.pipeline()
        pipe.setex(key, ttl, payload)

        # Track in company index (for admin cache invalidation)
        pipe.sadd(_company_index_key(company_id), key)
        pipe.expire(_company_index_key(company_id), ttl)

        # Track in team indexes (for per-team invalidation)
        for tid in (user.get("team_ids") or []):
            pipe.sadd(_team_index_key(tid), key)
            pipe.expire(_team_index_key(tid), ttl)

        await pipe.execute()
        logger.debug(f"Cache SET [{user.get('username')}]: {query[:60]}")
    except Exception as e:
        logger.warning(f"Cache set failed: {e}")


async def invalidate_team_cache(team_id: str) -> int:
    """
    Invalidate all cached answers that include this team's documents.
    Called when a document is uploaded or deleted.
    """
    try:
        r = await get_redis()
        index_key = _team_index_key(team_id)
        keys = await r.smembers(index_key)
        if keys:
            await r.delete(*keys)
            await r.delete(index_key)
        logger.info(f"Cache invalidated {len(keys)} entries for team {team_id}")
        return len(keys)
    except Exception as e:
        logger.warning(f"Cache invalidation failed: {e}")
        return 0


async def invalidate_company_cache(company_id: str) -> int:
    """Invalidate all cached answers for an entire company."""
    try:
        r = await get_redis()
        index_key = _company_index_key(company_id)
        keys = await r.smembers(index_key)
        if keys:
            await r.delete(*keys)
            await r.delete(index_key)
        logger.info(f"Cache invalidated {len(keys)} entries for company {company_id}")
        return len(keys)
    except Exception as e:
        logger.warning(f"Cache invalidation failed: {e}")
        return 0


async def get_cache_stats() -> dict:
    try:
        r = await get_redis()
        keys = await r.keys(f"{CACHE_PREFIX}*")
        return {"cached_queries": len(keys), "ttl_seconds": CACHE_TTL}
    except Exception:
        return {"cached_queries": 0, "ttl_seconds": CACHE_TTL}
