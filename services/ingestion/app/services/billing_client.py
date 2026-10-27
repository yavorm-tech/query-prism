import logging
import httpx
from fastapi import HTTPException
from app.config import get_settings

logger = logging.getLogger(__name__)


def _billing_url(path: str) -> str:
    return f"{get_settings().billing_url}{path}"


def _headers() -> dict:
    return {"X-Internal-Token": get_settings().internal_api_token}


async def check_storage_limit(company_id: str, file_size_bytes: int) -> None:
    async with httpx.AsyncClient(timeout=5.0) as client:
        r = await client.post(
            _billing_url("/internal/check/storage"),
            json={"company_id": company_id, "file_size_bytes": file_size_bytes},
            headers=_headers(),
        )
    if r.status_code == 413:
        raise HTTPException(413, r.json().get("detail", "Storage limit reached"))
    if not r.is_success:
        raise HTTPException(502, "Billing service error")


async def increment_storage(company_id: str, file_size_bytes: int) -> None:
    async with httpx.AsyncClient(timeout=5.0) as client:
        r = await client.post(
            _billing_url("/internal/storage/increment"),
            json={"company_id": company_id, "file_size_bytes": file_size_bytes},
            headers=_headers(),
        )
    r.raise_for_status()


async def decrement_storage(company_id: str, file_size_bytes: int) -> None:
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            await client.post(
                _billing_url("/internal/storage/decrement"),
                json={"company_id": company_id, "file_size_bytes": file_size_bytes},
                headers=_headers(),
            )
    except httpx.HTTPError as e:
        logger.warning(f"Failed to decrement storage for company {company_id}: {e}")
