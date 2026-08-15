import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../backend')))

import pytest
import datetime
import secrets
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.database.session import Base, get_db
from app.database import models
from app.config.config import settings
from app.security.auth_utils import hash_password, verify_password, hash_token
from app.api.auth import get_or_sync_admin

TEST_DATABASE_URL = "sqlite:///./test_auth_temp.db"
engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@pytest.fixture(scope="function")
def db_session():
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    
    # Configure test environment
    old_env = settings.ENV
    old_username = settings.AUTO_ZOHO_ADMIN_USERNAME
    old_email = settings.AUTO_ZOHO_ADMIN_EMAIL
    old_secret = settings.ADMIN_INITIALIZATION_SECRET
    
    settings.ENV = "test"
    settings.AUTO_ZOHO_ADMIN_USERNAME = "testadmin"
    settings.AUTO_ZOHO_ADMIN_EMAIL = "test@example.com"
    settings.ADMIN_INITIALIZATION_SECRET = "testsecret"
    
    yield db
    
    db.close()
    Base.metadata.drop_all(bind=engine)
    engine.dispose()
    
    settings.ENV = old_env
    settings.AUTO_ZOHO_ADMIN_USERNAME = old_username
    settings.AUTO_ZOHO_ADMIN_EMAIL = old_email
    settings.ADMIN_INITIALIZATION_SECRET = old_secret
    
    if os.path.exists("./test_auth_temp.db"):
        try:
            os.remove("./test_auth_temp.db")
        except OSError:
            pass

@pytest.fixture(scope="function")
def client(db_session):
    from app.api.deps import get_current_admin
    # Clear the global auth mock override to enforce real session verification
    if get_current_admin in app.dependency_overrides:
        del app.dependency_overrides[get_current_admin]
    app.dependency_overrides[get_db] = lambda: db_session
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()

def test_admin_single_row_uniqueness_and_sync(db_session):
    """Verifies get_or_sync_admin maintains exactly one row and syncs with environment variables."""
    # 1. First run creates the row
    admin = get_or_sync_admin(db_session)
    assert admin.username == "testadmin"
    assert admin.email == "test@example.com"
    assert admin.password_initialized is False
    
    # 2. Check exactly one row exists
    count = db_session.query(models.AdminAuth).count()
    assert count == 1
    
    # 3. Modify environment variables and check sync
    settings.AUTO_ZOHO_ADMIN_USERNAME = "newadmin"
    settings.AUTO_ZOHO_ADMIN_EMAIL = "new@example.com"
    
    admin2 = get_or_sync_admin(db_session)
    assert admin2.username == "newadmin"
    assert admin2.email == "new@example.com"
    assert admin2.id == admin.id
    
    # Check count remains exactly 1
    assert db_session.query(models.AdminAuth).count() == 1

def test_password_initialization_flow(client, db_session):
    """Tests password setup constraints: status, invalid secrets, mismatch, and double-initialization."""
    # Check status initially uninitialized
    res = client.get("/api/auth/status")
    assert res.status_code == 200
    assert res.json()["initialized"] is False
    
    # Scenario A: Initialize with wrong initialization secret -> fails
    res = client.post("/api/auth/initialize", json={
        "new_password": "password123",
        "confirm_password": "password123",
        "initialization_secret": "wrongsecret"
    })
    assert res.status_code == 400
    assert "Invalid initialization secret" in res.json()["detail"]
    
    # Scenario B: Initialize with password mismatch -> fails
    res = client.post("/api/auth/initialize", json={
        "new_password": "password123",
        "confirm_password": "mismatch123",
        "initialization_secret": "testsecret"
    })
    assert res.status_code == 400
    assert "Passwords do not match" in res.json()["detail"]
    
    # Scenario C: Correct credentials -> succeeds
    res = client.post("/api/auth/initialize", json={
        "new_password": "password123",
        "confirm_password": "password123",
        "initialization_secret": "testsecret"
    })
    assert res.status_code == 200
    assert res.json()["status"] == "success"
    
    # Status should now be initialized
    res = client.get("/api/auth/status")
    assert res.json()["initialized"] is True
    
    # Scenario D: Subsequent initialization attempts must fail
    res = client.post("/api/auth/initialize", json={
        "new_password": "password999",
        "confirm_password": "password999",
        "initialization_secret": "testsecret"
    })
    assert res.status_code == 400
    assert "already been initialized" in res.json()["detail"]

def test_login_flow_credentials_and_rate_limits(client, db_session):
    """Tests credential checks, generic messages, session creation, and rate-limiting."""
    admin = get_or_sync_admin(db_session)
    admin.password_hash = hash_password("password123")
    admin.password_initialized = True
    db_session.commit()
    
    # Scenario A: Correct login credentials -> succeeds
    res = client.post("/api/auth/login", json={
        "username": "testadmin",
        "password": "password123"
    })
    assert res.status_code == 200
    assert "session_token" in client.cookies
    assert "csrf_token" in client.cookies
    
    # Check status endpoint shows authenticated
    res_status = client.get("/api/auth/status")
    assert res_status.json()["authenticated"] is True
    assert res_status.json()["username"] == "testadmin"
    
    # Scenario B: Wrong password -> fails (generic message)
    client.cookies.clear()
    res = client.post("/api/auth/login", json={
        "username": "testadmin",
        "password": "wrongpassword"
    })
    assert res.status_code == 400
    assert res.json()["detail"] == "Invalid username or password."
    
    # Scenario C: Wrong username -> fails (generic message)
    res = client.post("/api/auth/login", json={
        "username": "nonexistent",
        "password": "password123"
    })
    assert res.status_code == 400
    assert res.json()["detail"] == "Invalid username or password."
    
    # Scenario D: Brute Force: > 5 failures triggers rate limiting (429)
    client.cookies.clear()
    # Add 5 failed attempts
    for _ in range(5):
        client.post("/api/auth/login", json={"username": "testadmin", "password": "wrongpassword"})
        
    res_limit = client.post("/api/auth/login", json={"username": "testadmin", "password": "password123"})
    assert res_limit.status_code == 429
    assert "Too many failed login attempts" in res_limit.json()["detail"]

def test_logout_behavior(client, db_session):
    """Verifies that logout revokes active sessions and clears cookie state."""
    admin = get_or_sync_admin(db_session)
    admin.password_hash = hash_password("password123")
    admin.password_initialized = True
    db_session.commit()
    
    # Login
    client.post("/api/auth/login", json={"username": "testadmin", "password": "password123"})
    assert db_session.query(models.AuthSession).count() == 1
    
    # Logout
    res = client.post("/api/auth/logout")
    assert res.status_code == 200
    assert "session_token" not in client.cookies
    assert db_session.query(models.AuthSession).count() == 0

def test_session_expiry_and_inactivity_sliding_window(client, db_session):
    """Verifies session access, inactivity timeout thresholds, and session deletion on expiry."""
    admin = get_or_sync_admin(db_session)
    admin.password_hash = hash_password("password123")
    admin.password_initialized = True
    db_session.commit()
    
    # Login
    client.post("/api/auth/login", json={"username": "testadmin", "password": "password123"})
    session = db_session.query(models.AuthSession).first()
    assert session is not None
    
    # Age session activity by 31 minutes to trigger inactivity timeout
    session.last_activity_at = datetime.datetime.utcnow() - datetime.timedelta(minutes=31)
    db_session.commit()
    
    # Try calling a protected endpoint -> must reject and delete session
    res = client.get("/api/uploads/history")
    assert res.status_code == 401
    assert db_session.query(models.AuthSession).count() == 0

@patch("app.api.auth.send_reset_code_email")
def test_forgot_password_and_otp_reset_flow(mock_email, client, db_session):
    """Tests password recovery flow: OTP requests cooldown, verification count checks, and password resets."""
    admin = get_or_sync_admin(db_session)
    admin.password_hash = hash_password("oldpassword")
    admin.password_initialized = True
    db_session.commit()
    
    # 1. Request Code
    res = client.post("/api/auth/forgot-password")
    assert res.status_code == 200
    assert mock_email.called
    
    # Check cooldown: requesting again immediately returns 429
    res_cooldown = client.post("/api/auth/forgot-password")
    assert res_cooldown.status_code == 429
    
    # Retrieve the generated OTP from mock or database (hash matches)
    recent_token = db_session.query(models.PasswordResetToken).first()
    assert recent_token is not None
    
    # 2. OTP Verification Rate Limiting (5 failures triggers lockout)
    for _ in range(5):
        res_fail = client.post("/api/auth/verify-otp", json={"otp": "000000"})
        assert res_fail.status_code == 400
        
    res_lockout = client.post("/api/auth/verify-otp", json={"otp": "111111"})
    assert res_lockout.status_code == 400
    assert "Maximum attempts exceeded" in res_lockout.json()["detail"]
    
    # 3. Verify Correct OTP (we create a new reset request since first is locked out)
    db_session.query(models.PasswordResetToken).delete()
    db_session.commit()
    
    # Request code again
    res = client.post("/api/auth/forgot-password")
    assert res.status_code == 200
    
    recent_token = db_session.query(models.PasswordResetToken).filter(models.PasswordResetToken.used_at.is_(None)).first()
    assert recent_token is not None
    
    # Inject known OTP "123456"
    recent_token.token_hash = hash_token("123456")
    db_session.commit()
    
    res_verify = client.post("/api/auth/verify-otp", json={"otp": "123456"})
    assert res_verify.status_code == 200
    reset_token = res_verify.json()["reset_token"]
    assert len(reset_token) > 0
    
    # 4. Reset Password
    res_reset = client.post("/api/auth/reset-password", json={
        "reset_token": reset_token,
        "new_password": "newpassword123",
        "confirm_password": "newpassword123"
    })
    assert res_reset.status_code == 200
    
    # Confirm password is changed
    db_session.refresh(admin)
    assert verify_password("newpassword123", admin.password_hash)

def test_change_password_and_session_invalidation(client, db_session):
    """Tests changing password under active sessions and ensuring old sessions are invalidated."""
    admin = get_or_sync_admin(db_session)
    admin.password_hash = hash_password("password123")
    admin.password_initialized = True
    db_session.commit()
    
    # Login and create two sessions simulating two active devices
    client.post("/api/auth/login", json={"username": "testadmin", "password": "password123"})
    session1_id = client.cookies.get("session_token")
    
    # Create second session in database manually
    raw_session2 = "session-token-2-device"
    session2 = models.AuthSession(
        id=raw_session2,
        admin_id=admin.id,
        session_token_hash=hash_token(raw_session2),
        created_at=datetime.datetime.utcnow(),
        expires_at=datetime.datetime.utcnow() + datetime.timedelta(minutes=30),
        last_activity_at=datetime.datetime.utcnow()
    )
    db_session.add(session2)
    db_session.commit()
    
    assert db_session.query(models.AuthSession).count() == 2
    
    # Change password
    res = client.post("/api/auth/change-password", json={
        "current_password": "password123",
        "new_password": "brandnewpassword",
        "confirm_password": "brandnewpassword"
    })
    assert res.status_code == 200
    
    # Check that session2 was deleted, but session1 (current session) remains active
    assert db_session.query(models.AuthSession).filter(models.AuthSession.id == raw_session2).count() == 0
    assert db_session.query(models.AuthSession).filter(models.AuthSession.id == session1_id).count() == 1

def test_csrf_middleware_protection(client, db_session):
    """Verifies Double Submit Cookie CSRF protection prevents requests when enforced."""
    object.__setattr__(settings, "CSRF_ENFORCED", True)
    try:
        admin = get_or_sync_admin(db_session)
        admin.password_hash = hash_password("password123")
        admin.password_initialized = True
        db_session.commit()
        
        # Set cookies but don't provide the matching X-CSRF-Token header
        client.cookies.set("session_token", "fake-session-token")
        client.cookies.set("csrf_token", "valid-csrf-token")
        
        res = client.post("/api/excel/validate", data={})
        assert res.status_code == 403
        assert "CSRF validation failed" in res.json()["detail"]
        
        # Provide matching header -> passes CSRF check (fails on session auth 401 instead of CSRF 403)
        res_pass = client.post(
            "/api/excel/validate", 
            data={},
            headers={"X-CSRF-Token": "valid-csrf-token"}
        )
        assert res_pass.status_code == 401 # Rejected by auth, meaning it passed CSRF!
    finally:
        object.__setattr__(settings, "CSRF_ENFORCED", False)
