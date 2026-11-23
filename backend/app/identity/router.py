import logging
import asyncpg
from fastapi import APIRouter, HTTPException, status, Depends, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from app.shared.security import get_current_user, require_company_admin
from app.shared import events
from app.identity import sessions
from app.identity.tokens import (
    REFRESH_COOKIE, access_token_for, clear_refresh_cookie, issue_session, set_refresh_cookie,
)
from app.shared.config import get_settings
from app.identity.service import (
    create_company, create_team, create_user, create_oauth_user, authenticate_user,
    get_user_by_email, get_teams_for_company,
    get_team, get_team_members, add_team_member, remove_team_member,
    create_invite, get_invite_by_token, accept_invite, INVITE_EXPIRY_HOURS,
    set_default_team, get_company, list_invites_for_company,
    update_user_avatar, get_user_avatar, get_user_in_company,
    count_teams, count_users, get_user_by_id,
    create_password_reset_token, consume_reset_token,
)
from app.identity.api import CompanyRegistered
from app.metering import api as metering
from app.notification.api import send_invite_email, send_password_reset_email
from app.audit.api import log_event

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["auth"])


# ── Models ────────────────────────────────────────────────────────────────────

class CompanyRegisterRequest(BaseModel):
    company_name: str
    username: str
    email: str
    password: str


class LoginRequest(BaseModel):
    email: str
    password: str


class InviteAcceptRequest(BaseModel):
    username: str
    password: str


class InviteCreateRequest(BaseModel):
    email: str
    team_id: str
    role: str = "member"


class CreateTeamRequest(BaseModel):
    name: str
    description: str | None = None


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int = 0          # seconds until access_token expires


def _token_response(access_token: str) -> TokenResponse:
    return TokenResponse(access_token=access_token, expires_in=get_settings().access_token_minutes * 60)


class UserResponse(BaseModel):
    id: str
    username: str
    email: str
    company_id: str
    company_name: str | None = None
    plan: str = "starter"
    role: str
    team_ids: list[str]
    default_team_id: str | None = None
    avatar: str | None = None


class TeamResponse(BaseModel):
    id: str
    name: str
    description: str | None = None
    company_id: str
    member_count: int | None = None


class MemberResponse(BaseModel):
    id: str
    username: str
    email: str
    company_role: str
    team_role: str


class InviteResponse(BaseModel):
    id: str
    token: str
    email: str
    expires_at: str


class InviteListItem(BaseModel):
    id: str
    email: str
    role: str
    team_name: str
    invited_by_username: str
    status: str
    created_at: str
    expires_at: str
    accepted_at: str | None = None


class InvitePreviewResponse(BaseModel):
    company_name: str
    team_name: str
    email: str


# ── Helpers ───────────────────────────────────────────────────────────────────

async def register_company(
    company_name: str, username: str, email: str,
    *, password: str | None = None, google_id: str | None = None,
) -> dict:
    """Create company, owner, "General" team and subscription, and announce
    CompanyRegistered (workspace adds the default topic), all in one transaction.
    Shared by password and Google sign-up. Returns the owner user."""
    try:
        async with events.unit_of_work() as uow:
            conn = uow.conn
            company = await create_company(company_name, conn=conn)
            company_id = str(company["id"])
            if google_id is not None:
                user = await create_oauth_user(company_id, username, email, google_id, role="owner", conn=conn)
            else:
                user = await create_user(company_id, username, email, password, role="owner", conn=conn)
            team = await create_team(company_id, "General", "Default team", conn=conn)
            user_id, team_id = str(user["id"]), str(team["id"])
            await add_team_member(team_id, user_id, role="admin", conn=conn)
            await set_default_team(user_id, team_id, conn=conn)
            await metering.open_subscription(company_id, conn=conn)
            await uow.publish(CompanyRegistered(company_id=company_id, team_id=team_id, owner_id=user_id))
    except asyncpg.UniqueViolationError:
        # Lost a race with another sign-up for the same email; nothing was kept.
        raise HTTPException(400, "Email already registered")
    user["default_team_id"] = team["id"]
    logger.info(f"New company registered: {company['name']} by {user['email']}")
    return user


# ── Register ──────────────────────────────────────────────────────────────────

@router.post("/register", response_model=TokenResponse, status_code=201)
async def register(request: CompanyRegisterRequest, response: Response):
    if len(request.password) < 8:
        raise HTTPException(400, "Password must be at least 8 characters")

    existing = await get_user_by_email(request.email)
    if existing:
        raise HTTPException(400, "Email already registered")

    user = await register_company(
        request.company_name, request.username, request.email, password=request.password,
    )
    token = await issue_session(user, response)
    return _token_response(token)


# ── Login ─────────────────────────────────────────────────────────────────────

@router.post("/login", response_model=TokenResponse)
async def login(request: LoginRequest, response: Response):
    user = await authenticate_user(request.email, request.password)
    if not user:
        # Log failure if the email belongs to a real user
        existing = await get_user_by_email(request.email)
        if existing:
            await log_event(
                company_id=str(existing["company_id"]),
                event_type="user.login.failure",
                actor_email=request.email,
            )
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Incorrect email or password")

    token = await issue_session(user, response)

    await log_event(
        company_id=str(user["company_id"]),
        event_type="user.login.success",
        actor_id=str(user["id"]),
        actor_username=user["username"],
        actor_email=user["email"],
    )
    return _token_response(token)


# ── Session refresh / logout ───────────────────────────────────────────────────

def _unauthorized() -> JSONResponse:
    r = JSONResponse(status_code=401, content={"detail": "Session expired. Please sign in again."})
    clear_refresh_cookie(r)
    return r


@router.post("/refresh", response_model=TokenResponse)
async def refresh(request: Request, response: Response):
    """Exchange the refresh cookie for a new access token (and a new refresh cookie)."""
    raw = request.cookies.get(REFRESH_COOKIE)
    if not raw:
        return _unauthorized()
    rotated = await sessions.rotate(raw)
    if not rotated:
        return _unauthorized()
    user_id, new_raw = rotated
    user = await get_user_by_id(user_id)
    if not user or not user.get("is_active"):
        await sessions.end_all_sessions(user_id)
        return _unauthorized()
    set_refresh_cookie(response, new_raw)
    return _token_response(await access_token_for(user))


@router.post("/logout", status_code=204)
async def logout(request: Request, response: Response):
    raw = request.cookies.get(REFRESH_COOKIE)
    if raw:
        await sessions.end_session(raw)
    clear_refresh_cookie(response)


# ── Invite preview ────────────────────────────────────────────────────────────

@router.get("/invite/{token}", response_model=InvitePreviewResponse)
async def preview_invite(token: str):
    invite = await get_invite_by_token(token)
    if not invite:
        raise HTTPException(404, "Invite not found or expired")
    return InvitePreviewResponse(
        company_name=invite["company_name"],
        team_name=invite["team_name"],
        email=invite["email"],
    )


# ── Accept invite ─────────────────────────────────────────────────────────────

@router.post("/invite/{token}/accept", response_model=TokenResponse, status_code=201)
async def accept_invite_endpoint(token: str, request: InviteAcceptRequest, response: Response):
    invite = await get_invite_by_token(token)
    if not invite:
        raise HTTPException(404, "Invite not found or expired")

    existing = await get_user_by_email(invite["email"])
    if existing:
        raise HTTPException(400, "Email already registered — please log in instead")

    if len(request.password) < 8:
        raise HTTPException(400, "Password must be at least 8 characters")

    company_id = str(invite["company_id"])
    await metering.check_user_limit(company_id, await count_users(company_id))

    user = await create_user(
        company_id=str(invite["company_id"]),
        username=request.username,
        email=invite["email"],
        password=request.password,
        role=invite["role"] if invite["role"] in ("admin",) else "member",
    )
    await add_team_member(str(invite["team_id"]), str(user["id"]), role=invite["role"])
    await set_default_team(str(user["id"]), str(invite["team_id"]))
    await accept_invite(token)

    user["default_team_id"] = invite["team_id"]
    token_str = await issue_session(user, response)

    await log_event(
        company_id=str(invite["company_id"]),
        event_type="member.joined",
        actor_id=str(user["id"]),
        actor_username=user["username"],
        actor_email=user["email"],
        team_id=str(invite["team_id"]),
        resource_type="team",
        resource_name=invite["team_name"],
    )
    logger.info(f"Invite accepted: {invite['email']} joined team {invite['team_name']}")
    return _token_response(token_str)


# ── Current user ──────────────────────────────────────────────────────────────

@router.get("/me", response_model=UserResponse)
async def me(current_user: dict = Depends(get_current_user)):
    company = await get_company(current_user["company_id"])
    if not company:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Account no longer exists")
    avatar = await get_user_avatar(current_user["sub"])
    return UserResponse(
        id=current_user["sub"],
        username=current_user["username"],
        email=current_user.get("email", ""),
        company_id=current_user["company_id"],
        company_name=company["name"],
        plan=await metering.get_plan(current_user["company_id"]),
        role=current_user["role"],
        team_ids=current_user.get("team_ids", []),
        default_team_id=current_user.get("default_team_id"),
        avatar=avatar,
    )


class AvatarUpdateRequest(BaseModel):
    avatar: str


@router.put("/me/avatar", status_code=204)
async def update_avatar(
    request: AvatarUpdateRequest,
    current_user: dict = Depends(get_current_user),
):
    # base64 encodes ~4 chars per 3 bytes, so 1 MB binary ≈ 1.37 MB string
    if len(request.avatar) > int(1.5 * 1024 * 1024):
        raise HTTPException(413, "Image too large. Maximum size is 1 MB.")
    await update_user_avatar(current_user["sub"], request.avatar)


@router.delete("/me/avatar", status_code=204)
async def delete_avatar(current_user: dict = Depends(get_current_user)):
    await update_user_avatar(current_user["sub"], None)


# ── Invites ───────────────────────────────────────────────────────────────────

@router.get("/invites", response_model=list[InviteListItem])
async def list_invites_endpoint(current_user: dict = Depends(get_current_user)):
    require_company_admin(current_user)
    rows = await list_invites_for_company(current_user["company_id"])
    import datetime
    now = datetime.datetime.now(datetime.timezone.utc)
    result = []
    for r in rows:
        if r["accepted_at"]:
            s = "accepted"
        elif r["expires_at"] < now:
            s = "expired"
        else:
            s = "pending"
        result.append(InviteListItem(
            id=str(r["id"]),
            email=r["email"],
            role=r["role"],
            team_name=r["team_name"],
            invited_by_username=r["invited_by_username"],
            status=s,
            created_at=str(r["created_at"]),
            expires_at=str(r["expires_at"]),
            accepted_at=str(r["accepted_at"]) if r["accepted_at"] else None,
        ))
    return result


@router.post("/invite", response_model=InviteResponse)
async def send_invite(
    request: InviteCreateRequest,
    current_user: dict = Depends(get_current_user),
):
    require_company_admin(current_user)
    team = await get_team(request.team_id, current_user["company_id"])
    if not team:
        raise HTTPException(404, "Team not found")

    invite = await create_invite(
        company_id=current_user["company_id"],
        team_id=request.team_id,
        email=request.email,
        invited_by=current_user["sub"],
        role=request.role,
    )

    company = await get_company(current_user["company_id"])
    await send_invite_email(
        email=request.email,
        company_name=company["name"] if company else "your company",
        team_name=team["name"],
        invite_token=invite["token"],
        expires_hours=INVITE_EXPIRY_HOURS,
    )

    await log_event(
        company_id=current_user["company_id"],
        event_type="member.invited",
        actor_id=current_user["sub"],
        actor_username=current_user["username"],
        team_id=request.team_id,
        resource_type="invite",
        resource_name=request.email,
        metadata={"role": request.role, "team_name": team["name"]},
    )

    return InviteResponse(
        id=str(invite["id"]),
        token=invite["token"],
        email=invite["email"],
        expires_at=str(invite["expires_at"]),
    )


# ── Password reset ────────────────────────────────────────────────────────────

class ForgotPasswordRequest(BaseModel):
    email: str


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str


@router.post("/forgot-password", status_code=204)
async def forgot_password(request: ForgotPasswordRequest):
    user = await get_user_by_email(request.email)
    if not user:
        return  # Don't reveal whether email exists

    token = await create_password_reset_token(str(user["id"]))
    await send_password_reset_email(email=request.email, reset_token=token)

    await log_event(
        company_id=str(user["company_id"]),
        event_type="password_reset.requested",
        actor_id=str(user["id"]),
        actor_username=user["username"],
        actor_email=user["email"],
    )


@router.post("/reset-password", status_code=204)
async def reset_password(request: ResetPasswordRequest):
    if len(request.new_password) < 8:
        raise HTTPException(400, "Password must be at least 8 characters")

    user_id = await consume_reset_token(request.token, request.new_password)
    if not user_id:
        raise HTTPException(400, "Reset link is invalid or has expired")
    # A password reset ends every existing session (e.g. a stolen refresh token).
    await sessions.end_all_sessions(user_id)


# ── Teams ─────────────────────────────────────────────────────────────────────

@router.get("/teams", response_model=list[TeamResponse])
async def list_teams(current_user: dict = Depends(get_current_user)):
    all_teams = await get_teams_for_company(current_user["company_id"])
    if current_user["role"] in ("admin", "owner"):
        return [
            TeamResponse(
                id=str(t["id"]), name=t["name"], description=t.get("description"),
                company_id=current_user["company_id"], member_count=t.get("member_count"),
            )
            for t in all_teams
        ]
    user_team_ids = set(current_user.get("team_ids", []))
    return [
        TeamResponse(
            id=str(t["id"]), name=t["name"], description=t.get("description"),
            company_id=current_user["company_id"], member_count=t.get("member_count"),
        )
        for t in all_teams if str(t["id"]) in user_team_ids
    ]


@router.post("/teams", response_model=TeamResponse, status_code=201)
async def create_team_endpoint(
    request: CreateTeamRequest,
    current_user: dict = Depends(get_current_user),
):
    require_company_admin(current_user)
    await metering.check_team_limit(current_user["company_id"], await count_teams(current_user["company_id"]))
    team = await create_team(
        company_id=current_user["company_id"],
        name=request.name,
        description=request.description,
    )
    return TeamResponse(
        id=str(team["id"]), name=team["name"], description=team.get("description"),
        company_id=current_user["company_id"],
    )


@router.get("/teams/{team_id}/members", response_model=list[MemberResponse])
async def list_members(team_id: str, current_user: dict = Depends(get_current_user)):
    # can_access_team() is True for admins on any team id, so also pin the team to the caller's company.
    if not await get_team(team_id, current_user["company_id"]):
        raise HTTPException(404, "Team not found")
    if current_user.get("role") not in ("admin", "owner") and team_id not in (current_user.get("team_ids") or []):
        raise HTTPException(403, "Access denied")
    members = await get_team_members(team_id)
    return [
        MemberResponse(
            id=str(m["id"]), username=m["username"], email=m["email"],
            company_role=m["company_role"], team_role=m["team_role"],
        )
        for m in members
    ]


@router.post("/teams/{team_id}/members", status_code=204)
async def add_member(
    team_id: str,
    user_id: str,
    role: str = "member",
    current_user: dict = Depends(get_current_user),
):
    require_company_admin(current_user)
    team = await get_team(team_id, current_user["company_id"])
    if not team:
        raise HTTPException(404, "Team not found")
    if not await get_user_in_company(user_id, current_user["company_id"]):
        raise HTTPException(404, "User not found")
    await add_team_member(team_id, user_id, role)


@router.delete("/teams/{team_id}/members/{user_id}", status_code=204)
async def remove_member(
    team_id: str,
    user_id: str,
    current_user: dict = Depends(get_current_user),
):
    require_company_admin(current_user)
    team = await get_team(team_id, current_user["company_id"])
    if not team:
        raise HTTPException(404, "Team not found")
    removed_user = await get_user_in_company(user_id, current_user["company_id"])

    removed = await remove_team_member(team_id, user_id)
    if not removed:
        raise HTTPException(404, "Member not found")

    await log_event(
        company_id=current_user["company_id"],
        event_type="member.removed",
        actor_id=current_user["sub"],
        actor_username=current_user["username"],
        team_id=team_id,
        resource_type="user",
        resource_id=user_id,
        resource_name=removed_user["username"] if removed_user else None,
        metadata={"email": removed_user["email"] if removed_user else None,
                  "team_name": team["name"]},
    )
