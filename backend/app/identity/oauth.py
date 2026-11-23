from datetime import timedelta
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, HTTPException, Query, Response
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

from app.shared.config import get_settings
from app.shared.security import decode_token
from app.identity.router import _token_response, register_company
from app.identity import sessions
from app.identity.tokens import create_access_token, issue_session, set_refresh_cookie
from app.identity.service import get_user_by_email, get_user_by_google_id, link_google_account

router = APIRouter(prefix="/auth/oauth", tags=["oauth"])

GOOGLE_AUTH_URL  = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_INFO_URL  = "https://www.googleapis.com/oauth2/v2/userinfo"


@router.get("/google")
async def google_login():
    s = get_settings()
    params = {
        "client_id":     s.google_client_id,
        "redirect_uri":  s.google_redirect_url,
        "response_type": "code",
        "scope":         "openid email profile",
        "access_type":   "offline",
        "prompt":        "select_account",
    }
    return RedirectResponse(f"{GOOGLE_AUTH_URL}?{urlencode(params)}")


@router.get("/google/callback")
async def google_callback(
    code:  str | None = Query(None),
    error: str | None = Query(None),
):
    s = get_settings()
    if error or not code:
        return RedirectResponse(f"{s.frontend_url}/login?error=oauth_cancelled")

    async with httpx.AsyncClient() as client:
        token_res = await client.post(GOOGLE_TOKEN_URL, data={
            "code":          code,
            "client_id":     s.google_client_id,
            "client_secret": s.google_client_secret,
            "redirect_uri":  s.google_redirect_url,
            "grant_type":    "authorization_code",
        })
        if token_res.status_code != 200:
            return RedirectResponse(f"{s.frontend_url}/login?error=oauth_failed")

        info_res = await client.get(
            GOOGLE_INFO_URL,
            headers={"Authorization": f"Bearer {token_res.json()['access_token']}"},
        )
        if info_res.status_code != 200:
            return RedirectResponse(f"{s.frontend_url}/login?error=oauth_failed")
        info = info_res.json()

    email     = info.get("email")
    google_id = info.get("id")
    if not email or not google_id:
        return RedirectResponse(f"{s.frontend_url}/login?error=oauth_failed")

    # Look up existing user
    user = await get_user_by_google_id(google_id)
    if not user:
        user = await get_user_by_email(email)
        if user:
            await link_google_account(str(user["id"]), google_id)

    if user:
        if not user.get("is_active"):
            return RedirectResponse(f"{s.frontend_url}/login?error=account_inactive")
        # The session travels in the httpOnly refresh cookie, never in the URL;
        # the login page exchanges it for an access token via POST /auth/refresh.
        redirect = RedirectResponse(f"{s.frontend_url}/login?oauth=success")
        set_refresh_cookie(redirect, await sessions.start_session(str(user["id"])))
        return redirect

    # New user — issue a short-lived pending token
    pending = create_access_token(
        {
            "type":      "oauth_pending",
            "email":     email,
            "google_id": google_id,
            "name":      info.get("name", ""),
        },
        expires_delta=timedelta(minutes=15),
    )
    return RedirectResponse(f"{s.frontend_url}/onboarding?token={pending}")


class OAuthCompleteRequest(BaseModel):
    pending_token: str
    company_name:  str
    username:      str


@router.post("/complete")
async def complete_oauth(request: OAuthCompleteRequest, response: Response):
    try:
        payload = decode_token(request.pending_token)
    except Exception:
        raise HTTPException(400, "Invalid or expired token")

    if payload.get("type") != "oauth_pending":
        raise HTTPException(400, "Invalid token type")

    email     = payload["email"]
    google_id = payload["google_id"]

    if await get_user_by_email(email):
        raise HTTPException(400, "Email already registered — please log in instead")

    user = await register_company(request.company_name, request.username, email, google_id=google_id)
    token = await issue_session(user, response)
    return _token_response(token)
