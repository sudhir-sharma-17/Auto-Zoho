import smtplib
from email.mime.text import MIMEText
import logging
from app.config.config import settings

logger = logging.getLogger("app.services.email")

def send_reset_code_email(to_email: str, code: str) -> bool:
    """Sends a password reset OTP verification code via SMTP."""
    if not settings.SMTP_HOST:
        logger.warning(f"SMTP is not configured. Reset OTP code is: {code} (for development)")
        return False
        
    subject = "AUTO-ZOHO Administrator Password Reset Verification"
    body = (
        "Hello,\n\n"
        "You have requested to reset your AUTO-ZOHO administrator password.\n"
        f"Your verification code is: {code}\n\n"
        "This code will expire in 10 minutes.\n"
        "If you did not request this, please ignore this email.\n\n"
        "Regards,\n"
        "AUTO-ZOHO System"
    )
    
    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = settings.SMTP_FROM_EMAIL or "noreply@example.com"
    msg["To"] = to_email
    
    try:
        # Connect to SMTP server
        server = smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT)
        server.ehlo()
        # Start TLS if port is standard submission port (587)
        if settings.SMTP_PORT == 587:
            server.starttls()
            server.ehlo()
            
        if settings.SMTP_USERNAME and settings.SMTP_PASSWORD:
            server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
            
        server.sendmail(msg["From"], [to_email], msg.as_string())
        server.quit()
        logger.info(f"Successfully sent reset code email to {to_email}")
        return True
    except Exception as e:
        logger.error(f"Failed to send email via SMTP: {str(e)}")
        return False
