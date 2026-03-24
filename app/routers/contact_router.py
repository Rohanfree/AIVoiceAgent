"""
contact_router.py — Handles contact form submissions from the landing page.

On POST /api/contact, validates the payload and sends an email to the
configured contact address using Gmail SMTP + an App Password.

Setup required in .env:
  SMTP_USER=aiautomite@gmail.com      (or whichever Gmail sends the email)
  SMTP_PASSWORD=xxxx xxxx xxxx xxxx   (Google App Password — NOT your normal password)
  CONTACT_EMAIL=aiautomite@gmail.com  (the inbox that receives submissions)
"""

import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, EmailStr, field_validator

from app.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["Contact"])


# ── Request schema ───────────────────────────────────────────────────────────

class ContactRequest(BaseModel):
    name: str
    email: EmailStr
    phone: str = ""
    message: str

    @field_validator("name", "message")
    @classmethod
    def not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Field must not be empty")
        return v.strip()


# ── Endpoint ─────────────────────────────────────────────────────────────────

@router.post(
    "/contact",
    status_code=status.HTTP_200_OK,
    summary="Submit contact form",
    response_description="Confirmation that the message was sent",
)
async def submit_contact(payload: ContactRequest) -> dict:
    """
    Receives a contact form submission and forwards it by email to
    the configured CONTACT_EMAIL address using Gmail SMTP.
    """
    if not settings.smtp_user or not settings.smtp_password:
        # Log and return success so the front-end UX still works during dev
        logger.warning(
            "SMTP credentials not configured. Would have sent contact email from %s",
            payload.email,
        )
        return {"status": "ok", "detail": "Message received (email not configured)"}

    try:
        _send_email(payload)
        logger.info("Contact form email sent from %s", payload.email)
        return {"status": "ok", "detail": "Message sent successfully"}
    except Exception as exc:
        logger.error("Failed to send contact email: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Could not send email. Please try again later or email us directly.",
        ) from exc


# ── Email helper ─────────────────────────────────────────────────────────────

def _send_email(payload: ContactRequest) -> None:
    """Build and send the HTML email via Gmail SMTP (TLS)."""
    subject = f"New Contact Form Submission — {payload.name}"

    phone_line = f"<p><strong>Phone:</strong> {payload.phone}</p>" if payload.phone else ""

    html_body = f"""
    <html><body style="font-family: 'Helvetica Neue', Arial, sans-serif; color:#111; max-width:600px; margin:0 auto;">
      <div style="background:#1A4D3A; padding:24px 32px; border-radius:12px 12px 0 0;">
        <h1 style="margin:0; color:#fff; font-size:22px;">✉ New Message from Automite AI Website</h1>
      </div>
      <div style="background:#f9f9f9; padding:32px; border:1px solid #e0e0e0; border-top:none; border-radius:0 0 12px 12px;">
        <p><strong>Name:</strong> {payload.name}</p>
        <p><strong>Email:</strong> <a href="mailto:{payload.email}">{payload.email}</a></p>
        {phone_line}
        <hr style="border:none; border-top:1px solid #e0e0e0; margin:20px 0;" />
        <p><strong>Message:</strong></p>
        <blockquote style="margin:0; padding:16px; background:#fff; border-left:4px solid #1A4D3A; border-radius:4px; white-space:pre-wrap;">{payload.message}</blockquote>
      </div>
      <p style="font-size:12px; color:#999; text-align:center; margin-top:16px;">
        Sent automatically by Automite AI contact form
      </p>
    </body></html>
    """

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"Automite AI Website <{settings.smtp_user}>"
    msg["To"] = settings.contact_email
    msg["Reply-To"] = payload.email

    msg.attach(MIMEText(html_body, "html"))

    with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as server:
        server.ehlo()
        server.starttls()
        server.login(settings.smtp_user, settings.smtp_password)
        server.sendmail(settings.smtp_user, settings.contact_email, msg.as_string())
