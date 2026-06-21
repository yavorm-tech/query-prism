import logging
import httpx
from app.config import get_settings

logger = logging.getLogger(__name__)


def _notification_url(path: str) -> str:
    return f"{get_settings().notification_url}{path}"


async def send_invite_email(email: str, company_name: str, team_name: str, invite_token: str) -> None:
    app_url = get_settings().app_url
    accept_url = f"{app_url}/login?invite={invite_token}"
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            await client.post(
                _notification_url("/notification/invite"),
                json={
                    "email": email,
                    "company_name": company_name,
                    "team_name": team_name,
                    "accept_url": accept_url,
                },
            )
    except Exception as e:
        logger.warning(f"Failed to send invite email to {email}: {e}")


async def send_password_reset_email(email: str, reset_token: str) -> None:
    app_url = get_settings().app_url
    reset_url = f"{app_url}/reset-password?token={reset_token}"
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            await client.post(
                _notification_url("/notification/reset-password"),
                json={"email": email, "reset_url": reset_url},
            )
    except Exception as e:
        logger.warning(f"Failed to send password reset email to {email}: {e}")
