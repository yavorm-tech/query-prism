import httpx
from fastapi import HTTPException
from app.config import get_settings


def _billing_url(path: str) -> str:
    return f"{get_settings().billing_url}{path}"


async def check_query_limit(company_id: str) -> None:
    async with httpx.AsyncClient(timeout=5.0) as client:
        r = await client.post(_billing_url("/internal/check/queries"), json={"company_id": company_id})
    if r.status_code == 429:
        raise HTTPException(429, r.json().get("detail", "Query limit reached"))
    if not r.is_success:
        raise HTTPException(502, "Billing service error")


async def increment_query_count(company_id: str) -> None:
    async with httpx.AsyncClient(timeout=5.0) as client:
        await client.post(_billing_url("/internal/queries/increment"), json={"company_id": company_id})


async def get_company_model(company_id: str) -> str:
    async with httpx.AsyncClient(timeout=5.0) as client:
        r = await client.get(_billing_url(f"/internal/model/{company_id}"))
    if r.is_success:
        return r.json().get("model", "claude-haiku-4-5-20251001")
    return "claude-haiku-4-5-20251001"
