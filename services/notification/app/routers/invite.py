import logging
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.services.email import send_email
from app.config import get_settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/notification", tags=["notification"])


class InviteEmailRequest(BaseModel):
    email: str
    company_name: str
    team_name: str
    accept_url: str


class ResetPasswordEmailRequest(BaseModel):
    email: str
    reset_url: str


@router.post("/invite")
async def send_invite_email(req: InviteEmailRequest):
    app_name = get_settings().app_name
    subject = f"You've been invited to join {req.team_name} at {app_name}"
    body_html = f"""
    <div style="font-family: sans-serif; max-width: 480px; margin: 0 auto;">
      <h2 style="color: #1a1a2e;">You're invited!</h2>
      <p>You've been invited to join the <strong>{req.team_name}</strong> team
         at <strong>{req.company_name}</strong> on {app_name}.</p>
      <p style="margin: 24px 0;">
        <a href="{req.accept_url}"
           style="background:#4F8EF7;color:white;padding:12px 24px;border-radius:8px;
                  text-decoration:none;font-weight:600;">
          Accept Invitation
        </a>
      </p>
      <p style="color:#888;font-size:13px;">
        This link expires in 7 days. If you didn't expect this invitation, you can ignore this email.
      </p>
    </div>
    """
    body_text = (
        f"You've been invited to join {req.team_name} at {req.company_name} on {app_name}.\n\n"
        f"Accept your invitation: {req.accept_url}\n\n"
        f"This link expires in 7 days."
    )
    try:
        await send_email(req.email, subject, body_html, body_text)
    except Exception as e:
        logger.error(f"Failed to send invite email to {req.email}: {e}")
        raise HTTPException(500, "Failed to send invite email")
    return {"ok": True}


@router.post("/reset-password")
async def send_reset_email(req: ResetPasswordEmailRequest):
    app_name = get_settings().app_name
    subject = f"Reset your {app_name} password"
    body_html = f"""
    <div style="font-family: sans-serif; max-width: 480px; margin: 0 auto;">
      <h2 style="color: #1a1a2e;">Reset your password</h2>
      <p>We received a request to reset the password for your {app_name} account.</p>
      <p style="margin: 24px 0;">
        <a href="{req.reset_url}"
           style="background:#4F8EF7;color:white;padding:12px 24px;border-radius:8px;
                  text-decoration:none;font-weight:600;">
          Reset Password
        </a>
      </p>
      <p style="color:#888;font-size:13px;">
        This link expires in 1 hour. If you didn't request a password reset, you can ignore this email.
      </p>
    </div>
    """
    body_text = (
        f"Reset your AskYourBase password:\n\n"
        f"{req.reset_url}\n\n"
        f"This link expires in 1 hour."
    )
    try:
        await send_email(req.email, subject, body_html, body_text)
    except Exception as e:
        logger.error(f"Failed to send reset email to {req.email}: {e}")
        raise HTTPException(500, "Failed to send reset email")
    return {"ok": True}
