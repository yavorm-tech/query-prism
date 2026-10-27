import logging
import httpx
from fastapi import HTTPException
from app.config import get_settings

logger = logging.getLogger(__name__)

# Used when billing is unreachable: keep answering, but on the cheapest model.
FALLBACK_MODEL = "gpt-4o-mini"


def _billing_url(path: str) -> str:
    return f"{get_settings().billing_url}{path}"


def _headers() -> dict:
    return {"X-Internal-Token": get_settings().internal_api_token}


async def reserve_query(company_id: str) -> tuple[str, bool]:
    """
    Atomically consume one query from the company's quota.
    Returns (model, reserved). reserved is False when billing was unreachable
    and we failed open — callers must not release in that case.
    Raises 429 when the quota is exhausted.
    """
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.post(
                _billing_url("/internal/queries/reserve"),
                json={"company_id": company_id}, headers=_headers(),
            )
    except httpx.HTTPError as e:
        logger.error(f"Billing unreachable, failing open for company {company_id}: {e}")
        return FALLBACK_MODEL, False

    if r.status_code == 429:
        raise HTTPException(429, r.json().get("detail", "Query limit reached"))
    if not r.is_success:
        logger.error(f"Billing reserve failed ({r.status_code}), failing open for company {company_id}")
        return FALLBACK_MODEL, False
    return r.json().get("model") or FALLBACK_MODEL, True


async def release_query(company_id: str) -> None:
    """Return a reserved query that did not lead to an LLM call."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            await client.post(
                _billing_url("/internal/queries/release"),
                json={"company_id": company_id}, headers=_headers(),
            )
    except httpx.HTTPError as e:
        logger.warning(f"Failed to release query for company {company_id}: {e}")
