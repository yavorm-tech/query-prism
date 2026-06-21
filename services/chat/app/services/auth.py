from jose import JWTError, jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.config import get_settings

ALGORITHM = "HS256"
bearer_scheme = HTTPBearer(auto_error=True)


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, get_settings().secret_key, algorithms=[ALGORITHM])
    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        ) from e


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> dict:
    return decode_token(credentials.credentials)


def can_access_team(user: dict, team_id: str) -> bool:
    if user.get("role") in ("admin", "owner"):
        return True
    return team_id in (user.get("team_ids") or [])


def require_company_admin(user: dict) -> None:
    if user.get("role") not in ("admin", "owner"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Company admin access required")


def require_owner(user: dict) -> None:
    if user.get("role") != "owner":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Owner access required")


def get_accessible_team_ids(user: dict) -> list[str] | None:
    if user.get("role") in ("admin", "owner"):
        return None
    return user.get("team_ids") or []
