"""Internal billing endpoints — reachable only from other services, not via gateway.

Every request must carry the shared X-Internal-Token header.
"""
import hmac
import logging
from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel
from app.config import get_settings
from app.services.usage import (
    check_query_limit, check_storage_limit, check_team_limit, check_user_limit,
    increment_query_count, reserve_query, release_query,
    increment_storage, decrement_storage, get_model_for_company,
)

logger = logging.getLogger(__name__)


def verify_internal_token(x_internal_token: str = Header(default="")) -> None:
    if not hmac.compare_digest(x_internal_token, get_settings().internal_api_token):
        raise HTTPException(401, "Invalid internal token")


router = APIRouter(prefix="/internal", tags=["internal"], dependencies=[Depends(verify_internal_token)])


class CompanyRequest(BaseModel):
    company_id: str


class StorageRequest(BaseModel):
    company_id: str
    file_size_bytes: int


@router.post("/check/queries")
async def check_queries(req: CompanyRequest):
    await check_query_limit(req.company_id)
    return {"ok": True}


@router.post("/check/storage")
async def check_storage(req: StorageRequest):
    await check_storage_limit(req.company_id, req.file_size_bytes)
    return {"ok": True}


@router.post("/check/teams")
async def check_teams(req: CompanyRequest):
    await check_team_limit(req.company_id)
    return {"ok": True}


@router.post("/check/users")
async def check_users(req: CompanyRequest):
    await check_user_limit(req.company_id)
    return {"ok": True}


@router.post("/queries/reserve")
async def reserve_queries(req: CompanyRequest):
    """Atomically consume one query from the monthly quota and return the plan's model."""
    model = await reserve_query(req.company_id)
    return {"ok": True, "model": model}


@router.post("/queries/release")
async def release_queries(req: CompanyRequest):
    """Give back a reserved query that produced no LLM call (cache hit, no context, error)."""
    await release_query(req.company_id)
    return {"ok": True}


@router.post("/queries/increment")
async def increment_queries(req: CompanyRequest):
    await increment_query_count(req.company_id)
    return {"ok": True}


@router.post("/storage/increment")
async def increment_storage_endpoint(req: StorageRequest):
    await increment_storage(req.company_id, req.file_size_bytes)
    return {"ok": True}


@router.post("/storage/decrement")
async def decrement_storage_endpoint(req: StorageRequest):
    await decrement_storage(req.company_id, req.file_size_bytes)
    return {"ok": True}


@router.get("/model/{company_id}")
async def get_model(company_id: str):
    model = await get_model_for_company(company_id)
    return {"model": model}
