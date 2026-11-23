"""Token issuing — identity is the only context that creates JWTs."""
from datetime import datetime, timedelta, timezone

from fastapi import Response
from jose import jwt

from app.shared.config import get_settings
from app.shared.security import ACCESS_TOKEN_TYPE, ALGORITHM
from app.identity import sessions
from app.identity.service import get_user_team_ids

REFRESH_COOKIE = "qp_refresh"
REFRESH_COOKIE_PATH = "/auth"


def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    """Sign a JWT. Callers minting access tokens use issue_session/access_token_for instead."""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=get_settings().access_token_minutes)
    )
    to_encode["exp"] = expire
    return jwt.encode(to_encode, get_settings().secret_key, algorithm=ALGORITHM)


async def build_token_payload(user: dict) -> dict:
    team_ids = await get_user_team_ids(str(user["id"]))
    return {
        "type":            ACCESS_TOKEN_TYPE,
        "sub":             str(user["id"]),
        "username":        user["username"],
        "email":           user["email"],
        "company_id":      str(user["company_id"]),
        "team_ids":        team_ids,
        "role":            user["role"],
        "default_team_id": str(user["default_team_id"]) if user.get("default_team_id") else (team_ids[0] if team_ids else None),
    }


async def access_token_for(user: dict) -> str:
    """A fresh access token; team ids and role are re-read from the database."""
    return create_access_token(await build_token_payload(user))


def set_refresh_cookie(response: Response, raw: str) -> None:
    s = get_settings()
    response.set_cookie(
        REFRESH_COOKIE, raw,
        max_age=s.refresh_token_days * 24 * 3600,
        path=REFRESH_COOKIE_PATH,
        httponly=True,
        secure=s.refresh_cookie_is_secure,
        samesite="strict",
    )


def clear_refresh_cookie(response: Response) -> None:
    s = get_settings()
    response.delete_cookie(
        REFRESH_COOKIE, path=REFRESH_COOKIE_PATH,
        httponly=True, secure=s.refresh_cookie_is_secure, samesite="strict",
    )


async def issue_session(user: dict, response: Response) -> str:
    """Log the user in: start a refresh-token family (cookie) and return an access token."""
    set_refresh_cookie(response, await sessions.start_session(str(user["id"])))
    return await access_token_for(user)
