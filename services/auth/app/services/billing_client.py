import httpx
from fastapi import HTTPException
from app.config import get_settings


def _billing_url(path: str) -> str:
    return f"{get_settings().billing_url}{path}"


async def check_team_limit(company_id: str) -> None:
    async with httpx.AsyncClient(timeout=5.0) as client:
        r = await client.post(_billing_url("/internal/check/teams"), json={"company_id": company_id})
    if r.status_code == 429:
        raise HTTPException(429, r.json().get("detail", "Team limit reached"))
    if not r.is_success:
        raise HTTPException(502, "Billing service error")


async def check_user_limit(company_id: str) -> None:
    async with httpx.AsyncClient(timeout=5.0) as client:
        r = await client.post(_billing_url("/internal/check/users"), json={"company_id": company_id})
    if r.status_code == 429:
        raise HTTPException(429, r.json().get("detail", "User limit reached"))
    if not r.is_success:
        raise HTTPException(502, "Billing service error")
