import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../backend')))

import datetime
from unittest.mock import patch, MagicMock
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database.session import Base
from app.database import models
from app.services.zoho.client import ZohoOAuthService, ZohoExpenseClient, ZohoEntityResolver
from app.security import encryption

TEST_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@pytest.fixture(scope="function")
def db_session():
    # Reset caches
    ZohoEntityResolver.clear_cache()
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    yield db
    db.close()
    Base.metadata.drop_all(bind=engine)

def test_token_encryption_decryption():
    """Confirms Fernet token encryption and decryption values matches exactly."""
    raw_token = "zho-secret-refresh-token-1234567890"
    enc = encryption.encrypt_token(raw_token)
    assert enc != raw_token
    
    dec = encryption.decrypt_token(enc)
    assert dec == raw_token

def test_oauth_state_generation_and_expiry(db_session):
    """Tests OAuth state verification lifecycle and timeout thresholds."""
    # Generate state
    state = ZohoOAuthService.generate_state(db_session)
    assert len(state) == 32
    
    # Verify it exists in db
    pending = db_session.query(models.PendingState).filter(models.PendingState.state == state).first()
    assert pending is not None
    
    # State is valid on first check
    # Check duplicate state validate calls delete the state (one-time use)
    assert ZohoOAuthService.validate_state(db_session, state)
    assert not ZohoOAuthService.validate_state(db_session, state)

def test_oauth_state_expiry(db_session):
    """Ensures state codes older than 5 minutes fail validation."""
    state = ZohoOAuthService.generate_state(db_session)
    pending = db_session.query(models.PendingState).filter(models.PendingState.state == state).first()
    
    # Age the state by 6 minutes
    pending.created_at = datetime.datetime.utcnow() - datetime.timedelta(minutes=6)
    db_session.commit()
    
    # Check validation fails
    assert not ZohoOAuthService.validate_state(db_session, state)

@patch("httpx.post")
def test_oauth_code_exchange(mock_post, db_session):
    """Simulates exchange of code for access and refresh tokens, mapping to DB credentials."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "access_token": "mock-access-token",
        "refresh_token": "mock-refresh-token",
        "expires_in": 3600,
        "api_domain": "https://www.zohoapis.com"
    }
    mock_post.return_value = mock_response
    
    # Mock organization lookup
    with patch.object(ZohoExpenseClient, "get_organizations_direct", return_value=[
        {"organization_id": "987654", "name": "ABC Test Org"}
    ]):
        cred = ZohoOAuthService.exchange_code(db_session, "auth-code", "https://accounts.zoho.com")
        
        # Verify credential attributes
        assert cred.api_domain == "https://www.zohoapis.com"
        assert encryption.decrypt_token(cred.encrypted_access_token) == "mock-access-token"
        assert encryption.decrypt_token(cred.encrypted_refresh_token) == "mock-refresh-token"
        assert cred.organization_id == "987654"
        assert cred.organization_name == "ABC Test Org"

@patch("httpx.post")
def test_token_refresh_lifecycle(mock_post, db_session):
    """Mocks token auto-refresh triggers when access token approaches expiry limits."""
    # Seed DB with expired credential
    cred = models.ZohoCredential(
        api_domain="https://www.zohoapis.com",
        encrypted_access_token=encryption.encrypt_token("old-access"),
        encrypted_refresh_token=encryption.encrypt_token("my-refresh"),
        expires_at=datetime.datetime.utcnow() - datetime.timedelta(minutes=1), # Expired 1 min ago
        organization_id="12345",
        organization_name="Test Org"
    )
    db_session.add(cred)
    db_session.commit()
    
    # Mock token refresh response
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "access_token": "new-access-token",
        "expires_in": 3600
    }
    mock_post.return_value = mock_response
    
    # Trigger refresh implicitly
    token = ZohoOAuthService.refresh_access_token(db_session)
    assert token == "new-access-token"
    
    # Verify DB updated
    updated_cred = db_session.query(models.ZohoCredential).first()
    assert encryption.decrypt_token(updated_cred.encrypted_access_token) == "new-access-token"
    assert updated_cred.expires_at > datetime.datetime.utcnow()

def test_disconnect_behavior(db_session):
    """Ensures disconnect requests purge local credentials records."""
    # Seed database
    cred = models.ZohoCredential(
        api_domain="https://www.zohoapis.com",
        encrypted_access_token=encryption.encrypt_token("access"),
        encrypted_refresh_token=encryption.encrypt_token("refresh"),
        expires_at=datetime.datetime.utcnow() + datetime.timedelta(hours=1),
        organization_id="123",
        organization_name="Org"
    )
    db_session.add(cred)
    db_session.commit()
    
    with patch("httpx.post") as mock_post:
        ZohoOAuthService.revoke_token(db_session)
        
        # Verify DB is cleared
        assert db_session.query(models.ZohoCredential).count() == 0
        # Verify Zoho revocation URL was hit
        assert mock_post.called

@patch("httpx.get")
def test_reports_listing_filtering(mock_get, db_session):
    """Mocks Zoho report retrieval and status filters."""
    # Seed connection credentials
    cred = models.ZohoCredential(
        api_domain="https://www.zohoapis.com",
        encrypted_access_token=encryption.encrypt_token("access"),
        encrypted_refresh_token=encryption.encrypt_token("refresh"),
        expires_at=datetime.datetime.utcnow() + datetime.timedelta(hours=1),
        organization_id="123",
        organization_name="Org"
    )
    db_session.add(cred)
    db_session.commit()
    
    # Setup mock reports response
    mock_get.return_value = MagicMock(
        status_code=200,
        json=lambda: {
            "expensereports": [
                {"report_id": "rep1", "report_name": "Report Draft", "status": "draft", "start_date": "2026-08-01", "end_date": "2026-08-31"},
                {"report_id": "rep2", "report_name": "Report Rejected", "status": "rejected", "start_date": "2026-08-01", "end_date": "2026-08-31"},
                {"report_id": "rep3", "report_name": "Report Approved", "status": "approved", "start_date": "2026-08-01", "end_date": "2026-08-31"}
            ]
        }
    )
    
    reports = ZohoExpenseClient.get_reports(db_session)
    
    # Assert filtering: only allows draft, submitted, or approved reports
    # 'rejected' (rep2) is filtered out
    assert len(reports) == 2
    assert reports[0]["report_id"] == "rep1"
    assert reports[1]["report_id"] == "rep3"
