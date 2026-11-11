import logging
import httpx
from app.config.config import settings

logger = logging.getLogger("app.services.email")

def send_reset_code_email(to_email: str, code: str) -> bool:
    """Sends a password reset OTP verification code via Brevo REST API or falls back to logging in development."""
    subject = "Auto-Zoho Password Reset Code"
    body = (
        f"Your Auto-Zoho password reset code is: {code}\n\n"
        "This code expires in 10 minutes.\n\n"
        "If you did not request this password reset, ignore this email."
    )

    if not settings.BREVO_API_KEY:
        if settings.ENV in ["development", "test"]:
            logger.warning(
                f"[DEVELOPMENT ONLY] Brevo API Key not configured. "
                f"Password reset OTP is: {code} (for to_email: {to_email})"
            )
        else:
            logger.warning("Brevo API Key not configured. Reset email not sent.")
        return False

    url = "https://api.brevo.com/v3/smtp/email"
    headers = {
        "api-key": settings.BREVO_API_KEY,
        "content-type": "application/json",
        "accept": "application/json"
    }
    
    payload = {
        "sender": {
            "name": settings.BREVO_FROM_NAME or "Auto-Zoho",
            "email": settings.BREVO_FROM_EMAIL
        },
        "to": [
            {"email": to_email}
        ],
        "subject": subject,
        "textContent": body
    }

    try:
        response = httpx.post(url, headers=headers, json=payload, timeout=10.0)
        if response.status_code in [200, 201, 202]:
            logger.info(f"Successfully sent reset code email via Brevo REST API to client recipient")
            return True
        else:
            logger.error(
                f"Brevo API returned error status: {response.status_code}, Response: {response.text}"
            )
            return False
    except Exception as e:
        logger.error(f"Failed to send email via Brevo REST API: {str(e)}")
        return False
