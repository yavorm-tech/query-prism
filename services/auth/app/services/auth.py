from datetime import datetime, timedelta, timezone
from typing import Any
from jose import JWTError, jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.config import get_settings
from app.services.users import get_user_team_ids

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # 7 days

bearer_scheme = HTTPBearer(auto_error=True)
optional_bearer = HTTPBearer(auto_error=False)


def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode["exp"] = expire
    return jwt.encode(to_encode, get_settings().secret_key, algorithm=ALGORITHM)


def decode_token(token: str) -> dict[str, Any]:
    try:
        return jwt.decode(token, get_settings().secret_key, algorithms=[ALGORITHM])
    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from e


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


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> dict:
    return decode_token(credentials.credentials)


def require_company_admin(user: dict) -> None:
    if user.get("role") not in ("admin", "owner"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Company admin access required")


def require_owner(user: dict) -> None:
    if user.get("role") != "owner":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Owner access required")


def can_access_team(user: dict, team_id: str) -> bool:
    if user.get("role") in ("admin", "owner"):
        return True
    return team_id in (user.get("team_ids") or [])


def get_accessible_team_ids(user: dict) -> list[str] | None:
    if user.get("role") in ("admin", "owner"):
        return None
    return user.get("team_ids") or []
