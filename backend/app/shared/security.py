"""Authentication primitives shared by every context: JWT verification and access checks."""
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.shared.config import get_settings
from app.shared.db import set_tenant

ALGORITHM = "HS256"
ACCESS_TOKEN_TYPE = "access"
bearer_scheme = HTTPBearer(auto_error=True)


def decode_token(token: str) -> dict:
    try:
        # PyJWT verifies the signature and exp; only HS256 is accepted (no "none", no key confusion).
        return jwt.decode(token, get_settings().secret_key, algorithms=[ALGORITHM])
    except jwt.InvalidTokenError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from e


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> dict:
    claims = decode_token(credentials.credentials)
    # Only access tokens authenticate requests (not e.g. OAuth "oauth_pending" tokens).
    if claims.get("type") != ACCESS_TOKEN_TYPE:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    # Database row-level security scopes this request's queries to the caller's company.
    set_tenant(claims.get("company_id"))
    return claims


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
