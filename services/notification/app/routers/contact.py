import logging
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, EmailStr
from app.services.email import send_email
from app.config import get_settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/contact", tags=["contact"])


class EnterpriseInquiry(BaseModel):
    name: str
    email: EmailStr
    company_name: str
    company_size: str
    message: str


@router.post("/enterprise", status_code=200)
async def enterprise_contact(body: EnterpriseInquiry):
    if not body.name.strip() or not body.message.strip():
        raise HTTPException(400, "Name and message are required")

    settings = get_settings()

    html = f"""
    <h2 style="color:#1a1a2e">Enterprise Inquiry — AskYourBase</h2>
    <table style="border-collapse:collapse;font-family:sans-serif;font-size:14px">
      <tr><td style="padding:6px 12px;color:#666">Name</td><td style="padding:6px 12px">{body.name}</td></tr>
      <tr><td style="padding:6px 12px;color:#666">Email</td><td style="padding:6px 12px">{body.email}</td></tr>
      <tr><td style="padding:6px 12px;color:#666">Company</td><td style="padding:6px 12px">{body.company_name}</td></tr>
      <tr><td style="padding:6px 12px;color:#666">Company size</td><td style="padding:6px 12px">{body.company_size}</td></tr>
    </table>
    <p style="font-family:sans-serif;font-size:14px;margin-top:16px"><strong>Message:</strong></p>
    <p style="font-family:sans-serif;font-size:14px;white-space:pre-wrap">{body.message}</p>
    """

    text = (
        f"Enterprise Inquiry — AskYourBase\n\n"
        f"Name:         {body.name}\n"
        f"Email:        {body.email}\n"
        f"Company:      {body.company_name}\n"
        f"Company size: {body.company_size}\n\n"
        f"Message:\n{body.message}"
    )

    try:
        await send_email(
            to=settings.sales_email,
            subject=f"Enterprise Inquiry from {body.company_name} ({body.name})",
            body_html=html,
            body_text=text,
        )
    except Exception as e:
        logger.error(f"Failed to send enterprise inquiry: {e}")
        raise HTTPException(500, "Failed to send your inquiry. Please try again later.")

    return {"success": True}
