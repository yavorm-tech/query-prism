"""
Notification context: transactional email.

Public API for other contexts. Sending never raises: a mail outage must not
fail the invite or password-reset flow that triggered it.
"""
import logging
from html import escape
from app.notification.email import send_email
from app.shared.config import get_settings

logger = logging.getLogger(__name__)


def _expiry_text(hours: int) -> str:
    if hours % 24 == 0:
        days = hours // 24
        return f"{days} day" if days == 1 else f"{days} days"
    return f"{hours} hour" if hours == 1 else f"{hours} hours"


async def send_invite_email(
    email: str, company_name: str, team_name: str, invite_token: str, expires_hours: int,
) -> None:
    settings = get_settings()
    expires = _expiry_text(expires_hours)
    app_name = settings.app_name
    accept_url = f"{settings.app_url}/login?invite={invite_token}"
    subject = f"You've been invited to join {team_name} at {app_name}"
    team, company, url = escape(team_name), escape(company_name), escape(accept_url, quote=True)
    body_html = f"""
    <div style="font-family: sans-serif; max-width: 480px; margin: 0 auto;">
      <h2 style="color: #1a1a2e;">You're invited!</h2>
      <p>You've been invited to join the <strong>{team}</strong> team
         at <strong>{company}</strong> on {app_name}.</p>
      <p style="margin: 24px 0;">
        <a href="{url}"
           style="background:#4F8EF7;color:white;padding:12px 24px;border-radius:8px;
                  text-decoration:none;font-weight:600;">
          Accept Invitation
        </a>
      </p>
      <p style="color:#888;font-size:13px;">
        This link expires in {expires}. If you didn't expect this invitation, you can ignore this email.
      </p>
    </div>
    """
    body_text = (
        f"You've been invited to join {team_name} at {company_name} on {app_name}.\n\n"
        f"Accept your invitation: {accept_url}\n\n"
        f"This link expires in {expires}."
    )
    try:
        await send_email(email, subject, body_html, body_text)
    except Exception as e:
        logger.warning(f"Failed to send invite email to {email}: {e}")


async def send_password_reset_email(email: str, reset_token: str) -> None:
    settings = get_settings()
    app_name = settings.app_name
    reset_url = f"{settings.app_url}/reset-password?token={reset_token}"
    subject = f"Reset your {app_name} password"
    url = escape(reset_url, quote=True)
    body_html = f"""
    <div style="font-family: sans-serif; max-width: 480px; margin: 0 auto;">
      <h2 style="color: #1a1a2e;">Reset your password</h2>
      <p>We received a request to reset the password for your {app_name} account.</p>
      <p style="margin: 24px 0;">
        <a href="{url}"
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
        f"{reset_url}\n\n"
        f"This link expires in 1 hour."
    )
    try:
        await send_email(email, subject, body_html, body_text)
    except Exception as e:
        logger.warning(f"Failed to send password reset email to {email}: {e}")
