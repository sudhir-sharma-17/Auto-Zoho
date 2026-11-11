import pytest
from unittest.mock import patch, MagicMock
from app.config.config import settings
from app.services.email import send_reset_code_email

def test_send_reset_code_email_no_api_key():
    """Verify send_reset_code_email falls back to logging/warning when no API key is provided."""
    # Ensure BREVO_API_KEY is unset/empty
    with patch.object(settings, "BREVO_API_KEY", ""):
        with patch("app.services.email.logger") as mock_logger:
            result = send_reset_code_email("test@example.com", "123456")
            assert result is False
            assert mock_logger.warning.called
            # Ensure the OTP is printed in the development fallback warning
            warning_msg = mock_logger.warning.call_args[0][0]
            assert "123456" in warning_msg

def test_send_reset_code_email_success():
    """Verify send_reset_code_email calls Brevo API and returns True on success."""
    with patch.object(settings, "BREVO_API_KEY", "test_key"), \
         patch.object(settings, "BREVO_FROM_EMAIL", "sender@example.com"), \
         patch.object(settings, "BREVO_FROM_NAME", "Auto-Zoho-Test"):
        
        mock_response = MagicMock()
        mock_response.status_code = 201
        
        with patch("httpx.post", return_value=mock_response) as mock_post:
            result = send_reset_code_email("recipient@example.com", "987654")
            assert result is True
            
            # Verify mock_post parameters
            mock_post.assert_called_once()
            args, kwargs = mock_post.call_args
            assert args[0] == "https://api.brevo.com/v3/smtp/email"
            assert kwargs["headers"]["api-key"] == "test_key"
            
            payload = kwargs["json"]
            assert payload["sender"]["name"] == "Auto-Zoho-Test"
            assert payload["sender"]["email"] == "sender@example.com"
            assert payload["to"] == [{"email": "recipient@example.com"}]
            assert payload["subject"] == "Auto-Zoho Password Reset Code"
            assert "987654" in payload["textContent"]

def test_send_reset_code_email_api_error():
    """Verify send_reset_code_email returns False when Brevo API returns an error status code."""
    with patch.object(settings, "BREVO_API_KEY", "test_key"), \
         patch.object(settings, "BREVO_FROM_EMAIL", "sender@example.com"):
        
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.text = "Bad Request"
        
        with patch("httpx.post", return_value=mock_response) as mock_post:
            result = send_reset_code_email("recipient@example.com", "987654")
            assert result is False
