import httpx
from fastapi import HTTPException
from app.config import get_settings


def _billing_url(path: str) -> str:
    return f"{get_settings().billing_url}{path}"


async def check_storage_limit(company_id: str, file_size_bytes: int) -> None:
    async with httpx.AsyncClient(timeout=5.0) as client:
        r = await client.post(
            _billing_url("/internal/check/storage"),
            json={"company_id": company_id, "file_size_bytes": file_size_bytes},
        )
    if r.status_code == 413:
        raise HTTPException(413, r.json().get("detail", "Storage limit reached"))
    if not r.is_success:
        raise HTTPException(502, "Billing service error")


async def decrement_storage(company_id: str, file_size_bytes: int) -> None:
    async with httpx.AsyncClient(timeout=5.0) as client:
        await client.post(
            _billing_url("/internal/storage/decrement"),
            json={"company_id": company_id, "file_size_bytes": file_size_bytes},
        )


async def get_company_model(company_id: str) -> str:
    async with httpx.AsyncClient(timeout=5.0) as client:
        r = await client.get(_billing_url(f"/internal/model/{company_id}"))
    if r.is_success:
        return r.json().get("model", "claude-haiku-4-5-20251001")
    return "claude-haiku-4-5-20251001"
