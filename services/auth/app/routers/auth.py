import logging
from fastapi import APIRouter, HTTPException, status, Depends
from pydantic import BaseModel
from app.services.auth import (
    create_access_token, get_current_user,
    build_token_payload, require_company_admin, can_access_team,
)
from app.services.users import (
    create_company, create_team, create_user, authenticate_user,
    get_user_by_email, get_user_team_ids, get_teams_for_company,
    get_team, get_team_members, add_team_member, remove_team_member,
    create_invite, get_invite_by_token, accept_invite,
    set_default_team, get_company, list_invites_for_company,
    update_user_avatar, get_user_avatar,
)
from app.services.billing_client import check_team_limit, check_user_limit
from app.services.notification_client import send_invite_email, send_password_reset_email
from app.services.users import (
    create_password_reset_token, get_reset_token, consume_reset_token,
    get_user_by_email as _get_user_by_email,
)
from app.db.connection import get_pool
from app.services.audit import log_event

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

async def _create_default_topic(team_id: str, company_id: str, created_by: str) -> None:
    """Create a default 'Main' topic for the new team (inline to avoid service coupling)."""
    pool = await get_pool()
    import uuid
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO topics (id, team_id, company_id, name, description, created_by)
            VALUES ($1, $2, $3, $4, $5, $6)
            ON CONFLICT DO NOTHING
            """,
            str(uuid.uuid4()), team_id, company_id, "Main", "Default topic", created_by,
        )


# ── Register ──────────────────────────────────────────────────────────────────

@router.post("/register", response_model=TokenResponse, status_code=201)
async def register(request: CompanyRegisterRequest):
    if len(request.password) < 8:
        raise HTTPException(400, "Password must be at least 8 characters")

    existing = await get_user_by_email(request.email)
    if existing:
        raise HTTPException(400, "Email already registered")

    company = await create_company(request.company_name)
    user = await create_user(
        company_id=str(company["id"]),
        username=request.username,
        email=request.email,
        password=request.password,
        role="owner",
    )
    team = await create_team(
        company_id=str(company["id"]),
        name="General",
        description="Default team",
    )
    await add_team_member(str(team["id"]), str(user["id"]), role="admin")
    await _create_default_topic(str(team["id"]), str(company["id"]), str(user["id"]))
    await set_default_team(str(user["id"]), str(team["id"]))

    user["default_team_id"] = team["id"]
    payload = await build_token_payload(user)
    token = create_access_token(payload)

    logger.info(f"New company registered: {company['name']} by {user['email']}")
    return TokenResponse(access_token=token)


# ── Login ─────────────────────────────────────────────────────────────────────

@router.post("/login", response_model=TokenResponse)
async def login(request: LoginRequest):
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

    payload = await build_token_payload(user)
    token = create_access_token(payload)

    await log_event(
        company_id=str(user["company_id"]),
        event_type="user.login.success",
        actor_id=str(user["id"]),
        actor_username=user["username"],
        actor_email=user["email"],
    )
    return TokenResponse(access_token=token)


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
async def accept_invite_endpoint(token: str, request: InviteAcceptRequest):
    invite = await get_invite_by_token(token)
    if not invite:
        raise HTTPException(404, "Invite not found or expired")

    existing = await get_user_by_email(invite["email"])
    if existing:
        raise HTTPException(400, "Email already registered — please log in instead")

    if len(request.password) < 8:
        raise HTTPException(400, "Password must be at least 8 characters")

    await check_user_limit(str(invite["company_id"]))

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
    payload = await build_token_payload(user)
    token_str = create_access_token(payload)

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
    return TokenResponse(access_token=token_str)


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
        plan=company["plan"],
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
    user = await _get_user_by_email(request.email)
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

    ok = await consume_reset_token(request.token, request.new_password)
    if not ok:
        raise HTTPException(400, "Reset link is invalid or has expired")


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
    await check_team_limit(current_user["company_id"])
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
    if not can_access_team(current_user, team_id):
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
    await check_user_limit(current_user["company_id"])
    await add_team_member(team_id, user_id, role)


@router.delete("/teams/{team_id}/members/{user_id}", status_code=204)
async def remove_member(
    team_id: str,
    user_id: str,
    current_user: dict = Depends(get_current_user),
):
    require_company_admin(current_user)
    from app.services.users import remove_team_member as _remove

    # Fetch member info before removing for audit record
    pool = await get_pool()
    async with pool.acquire() as conn:
        removed_user = await conn.fetchrow(
            "SELECT u.username, u.email, t.name AS team_name FROM users u, teams t WHERE u.id = $1 AND t.id = $2",
            user_id, team_id,
        )

    removed = await _remove(team_id, user_id)
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
                  "team_name": removed_user["team_name"] if removed_user else None},
    )
