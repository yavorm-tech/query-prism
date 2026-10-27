import httpx
from fastapi import HTTPException
from app.config import get_settings

# Billing answers 403 for plan limits and 429 for rate-style limits; both carry a
# user-facing detail payload that the frontend renders, so pass them through.
_LIMIT_STATUSES = (403, 429)


def _billing_url(path: str) -> str:
    return f"{get_settings().billing_url}{path}"


def _headers() -> dict:
    return {"X-Internal-Token": get_settings().internal_api_token}


async def check_team_limit(company_id: str) -> None:
    async with httpx.AsyncClient(timeout=5.0) as client:
        r = await client.post(_billing_url("/internal/check/teams"), json={"company_id": company_id}, headers=_headers())
    if r.status_code in _LIMIT_STATUSES:
        raise HTTPException(r.status_code, r.json().get("detail", "Team limit reached"))
    if not r.is_success:
        raise HTTPException(502, "Billing service error")


async def check_user_limit(company_id: str) -> None:
    async with httpx.AsyncClient(timeout=5.0) as client:
        r = await client.post(_billing_url("/internal/check/users"), json={"company_id": company_id}, headers=_headers())
    if r.status_code in _LIMIT_STATUSES:
        raise HTTPException(r.status_code, r.json().get("detail", "User limit reached"))
    if not r.is_success:
        raise HTTPException(502, "Billing service error")
