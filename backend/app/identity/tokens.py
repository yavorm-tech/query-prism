"""Token issuing — identity is the only context that creates JWTs."""
from datetime import datetime, timedelta, timezone
from jose import jwt
from app.shared.config import get_settings
from app.shared.security import ALGORITHM
from app.identity.service import get_user_team_ids

ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # 7 days


def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode["exp"] = expire
    return jwt.encode(to_encode, get_settings().secret_key, algorithm=ALGORITHM)


async def build_token_payload(user: dict) -> dict:
    team_ids = await get_user_team_ids(str(user["id"]))
    return {
        "sub":             str(user["id"]),
        "username":        user["username"],
        "email":           user["email"],
        "company_id":      str(user["company_id"]),
        "team_ids":        team_ids,
        "role":            user["role"],
        "default_team_id": str(user["default_team_id"]) if user.get("default_team_id") else (team_ids[0] if team_ids else None),
    }
