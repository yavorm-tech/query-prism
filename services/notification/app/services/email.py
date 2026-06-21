import smtplib
import logging
import asyncio
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from app.config import get_settings

logger = logging.getLogger(__name__)


def _send_sync(to: str, subject: str, body_html: str, body_text: str) -> None:
    s = get_settings()
    msg = MIMEMultipart('alternative')
    msg['Subject'] = subject
    msg['From'] = s.smtp_from_email
    msg['To'] = to
    if body_text:
        msg.attach(MIMEText(body_text, 'plain'))
    msg.attach(MIMEText(body_html, 'html'))

    with smtplib.SMTP(s.smtp_host, s.smtp_port, timeout=10) as server:
        if s.smtp_use_tls:
            server.starttls()
        if s.smtp_username and s.smtp_password:
            server.login(s.smtp_username, s.smtp_password)
        server.sendmail(s.smtp_from_email, [to], msg.as_string())
    logger.info(f"Email sent to {to}: {subject}")


async def send_email(to: str, subject: str, body_html: str, body_text: str = '') -> None:
    await asyncio.to_thread(_send_sync, to, subject, body_html, body_text)
