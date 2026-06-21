from fastapi import APIRouter, Depends
from app.services.auth import get_current_user
from app.services.usage import get_usage

router = APIRouter(prefix="/usage", tags=["usage"])


@router.get("")
async def get_usage_endpoint(current_user: dict = Depends(get_current_user)):
    return await get_usage(current_user["company_id"])
