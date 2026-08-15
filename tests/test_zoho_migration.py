import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../backend')))

import datetime
import sqlite3
from unittest.mock import patch, MagicMock
import pytest
from sqlalchemy import create_engine, text, inspect
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

from app.main import app
from app.database.session import get_db, Base
from app.database import models
from app.database.migrations import run_migrations
from app.services.zoho.client import ZohoOAuthService, ZohoExpenseClient, ZohoEntityResolver
from app.security import encryption

TEST_MIGRATE_DB_URL = "sqlite:///./test_migrate_temp.db"

@pytest.fixture(scope="function")
def old_db_engine():
    # Reset caches
    ZohoEntityResolver.clear_cache()
    # Ensure any old test file is deleted
    if os.path.exists("./test_migrate_temp.db"):
        try:
            os.remove("./test_migrate_temp.db")
        except OSError:
            pass
            
    engine = create_engine(TEST_MIGRATE_DB_URL, connect_args={"check_same_thread": False})
    
    # 1. Create a schema without the 'scopes' column in 'zoho_credentials'
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE upload_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_name VARCHAR(255) NOT NULL,
                timestamp DATETIME NOT NULL,
                total_rows INTEGER NOT NULL,
                valid_rows INTEGER NOT NULL,
                invalid_rows INTEGER NOT NULL,
                gst_count INTEGER NOT NULL,
                nongst_count INTEGER NOT NULL,
                status VARCHAR(50) NOT NULL,
                error_report_path VARCHAR(500)
            )
        """))
        
        conn.execute(text("""
            CREATE TABLE expense_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER NOT NULL,
                original_row_number INTEGER NOT NULL,
                expense_date VARCHAR(100),
                amount FLOAT,
                description TEXT,
                gst_type VARCHAR(50),
                category VARCHAR(255),
                tax_type VARCHAR(255),
                paid_through VARCHAR(255),
                project VARCHAR(255),
                expense_kind VARCHAR(255),
                vendor_name VARCHAR(255),
                status VARCHAR(50) NOT NULL,
                errors TEXT
            )
        """))
        
        # 'zoho_credentials' table WITHOUT 'scopes' column
        conn.execute(text("""
            CREATE TABLE zoho_credentials (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                api_domain VARCHAR(255) NOT NULL,
                encrypted_access_token TEXT NOT NULL,
                encrypted_refresh_token TEXT NOT NULL,
                expires_at DATETIME NOT NULL,
                organization_id VARCHAR(100),
                organization_name VARCHAR(255),
                connected_at DATETIME NOT NULL
            )
        """))
        
        conn.execute(text("""
            CREATE TABLE pending_oauth_states (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                state VARCHAR(100) NOT NULL UNIQUE,
                created_at DATETIME NOT NULL
            )
        """))
        
        conn.execute(text("""
            CREATE TABLE zoho_audit_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME NOT NULL,
                excel_row INTEGER NOT NULL,
                amount FLOAT NOT NULL,
                description VARCHAR(500) NOT NULL,
                destination_report VARCHAR(255) NOT NULL,
                result VARCHAR(50) NOT NULL,
                zoho_expense_id VARCHAR(100),
                error_details TEXT
            )
        """))
        
        # 2. Seed dummy records to verify data preservation
        conn.execute(text("""
            INSERT INTO upload_sessions (file_name, timestamp, total_rows, valid_rows, invalid_rows, gst_count, nongst_count, status)
            VALUES ('historical_run.xlsx', '2026-08-01 12:00:00', 10, 8, 2, 5, 5, 'Validated')
        """))
        
        conn.execute(text("""
            INSERT INTO zoho_credentials (api_domain, encrypted_access_token, encrypted_refresh_token, expires_at, organization_id, organization_name, connected_at)
            VALUES ('https://www.zohoapis.in', 'enc-access', 'enc-refresh', '2026-08-01 13:00:00', 'org-123', 'Old Org', '2026-08-01 12:00:00')
        """))
        
        conn.execute(text("""
            INSERT INTO zoho_audit_logs (timestamp, excel_row, amount, description, destination_report, result, zoho_expense_id)
            VALUES ('2026-08-01 12:05:00', 3, 150.0, 'Office supplies', 'Report A', 'SUCCESS', 'zoho-exp-abc')
        """))

    yield engine
    
    # Teardown
    engine.dispose()
    if os.path.exists("./test_migrate_temp.db"):
        try:
            os.remove("./test_migrate_temp.db")
        except OSError:
            pass

def test_database_migration_preserves_data(old_db_engine):
    """Verifies that running migrations on an old DB schema adds the scopes column without losing data."""
    # Run migration on the old DB
    run_migrations(old_db_engine)
    
    # Verify the column exists now
    inspector = inspect(old_db_engine)
    columns = [col["name"] for col in inspector.get_columns("zoho_credentials")]
    assert "scopes" in columns
    
    # Verify existing data is preserved intact
    TestingSession = sessionmaker(bind=old_db_engine)
    session = TestingSession()
    try:
        # Check upload sessions table has our seeded record
        upload = session.execute(text("SELECT file_name, total_rows FROM upload_sessions")).fetchone()
        assert upload is not None
        assert upload[0] == "historical_run.xlsx"
        assert upload[1] == 10
        
        # Check audit logs table has our seeded record
        audit = session.execute(text("SELECT excel_row, amount, zoho_expense_id FROM zoho_audit_logs")).fetchone()
        assert audit is not None
        assert audit[0] == 3
        assert audit[1] == 150.0
        assert audit[2] == "zoho-exp-abc"
        
        # Check credentials table has our seeded record and scopes defaults to empty string
        cred = session.execute(text("SELECT api_domain, organization_name, scopes FROM zoho_credentials")).fetchone()
        assert cred is not None
        assert cred[0] == "https://www.zohoapis.in"
        assert cred[1] == "Old Org"
        assert cred[2] == "" # default value applied safely
    finally:
        session.close()

@patch("httpx.post")
def test_oauth_credential_storage_with_scopes(mock_post, old_db_engine):
    """Verifies OAuth code exchange stores scopes and updates connected_at timestamp."""
    run_migrations(old_db_engine)
    
    TestingSession = sessionmaker(bind=old_db_engine)
    db = TestingSession()
    
    try:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "access_token": "new-access",
            "refresh_token": "new-refresh",
            "expires_in": 3600,
            "api_domain": "https://www.zohoapis.in",
            "scope": "ZohoExpense.expense.CREATE ZohoExpense.expensereport.READ"
        }
        mock_post.return_value = mock_response
        
        with patch.object(ZohoExpenseClient, "get_organizations_direct", return_value=[
            {"organization_id": "org-999", "name": "New Org Name"}
        ]):
            cred = ZohoOAuthService.exchange_code(db, "test-auth-code", "https://accounts.zoho.in")
            
            assert cred.scopes == "ZohoExpense.expense.CREATE ZohoExpense.expensereport.READ"
            assert encryption.decrypt_token(cred.encrypted_access_token) == "new-access"
            assert encryption.decrypt_token(cred.encrypted_refresh_token) == "new-refresh"
            assert cred.organization_id == "org-999"
            assert cred.organization_name == "New Org Name"
            # Ensure connected_at is close to current time (within 10 seconds)
            time_diff = datetime.datetime.utcnow() - cred.connected_at
            assert time_diff.total_seconds() < 10
    finally:
        db.close()

def test_api_status_does_not_fail(old_db_engine):
    """Verifies that GET /api/zoho/status returns 200 OK after migration."""
    run_migrations(old_db_engine)
    
    TestingSession = sessionmaker(bind=old_db_engine)
    
    def override_get_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()
            
    app.dependency_overrides[get_db] = override_get_db
    
    with TestClient(app) as client:
        # Before seeding/connecting
        # Let's clear credentials to test "not connected" state
        db = TestingSession()
        db.execute(text("DELETE FROM zoho_credentials"))
        db.commit()
        db.close()
        
        res = client.get("/api/zoho/status")
        assert res.status_code == 200
        assert res.json() == {"connected": False, "organization": None}
        
        # After seeding credentials
        db = TestingSession()
        # Seed valid credential
        enc_access = encryption.encrypt_token("access-123")
        enc_refresh = encryption.encrypt_token("refresh-123")
        db.execute(text(f"""
            INSERT INTO zoho_credentials (api_domain, encrypted_access_token, encrypted_refresh_token, expires_at, organization_id, organization_name, scopes, connected_at)
            VALUES ('https://www.zohoapis.in', '{enc_access}', '{enc_refresh}', '2030-01-01 12:00:00', 'org-123', 'My Valid Org', 'ZohoExpense.expense.CREATE', '2026-08-14 12:00:00')
        """))
        db.commit()
        db.close()
        
        res = client.get("/api/zoho/status")
        assert res.status_code == 200
        data = res.json()
        assert data["connected"] is True
        assert data["organization"] == "My Valid Org"
        
    app.dependency_overrides.clear()

@patch("httpx.post")
def test_oauth_callback_stores_scopes(mock_post, old_db_engine):
    """Verifies that the /api/zoho/callback endpoint executes exchange correctly and stores scopes."""
    run_migrations(old_db_engine)
    
    TestingSession = sessionmaker(bind=old_db_engine)
    
    def override_get_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()
            
    app.dependency_overrides[get_db] = override_get_db
    
    db = TestingSession()
    # Seed a pending OAuth state
    pending = models.PendingState(state="valid-test-state")
    db.add(pending)
    db.commit()
    db.close()
    
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "access_token": "callback-access",
        "refresh_token": "callback-refresh",
        "expires_in": 3600,
        "api_domain": "https://www.zohoapis.in",
        "scope": "ZohoExpense.expense.CREATE ZohoExpense.expensereport.READ"
    }
    mock_post.return_value = mock_response
    
    with patch.object(ZohoExpenseClient, "get_organizations_direct", return_value=[
        {"organization_id": "org-777", "name": "Callback Org"}
    ]):
        with TestClient(app) as client:
            res = client.get(
                "/api/zoho/callback?code=mock-code&state=valid-test-state&accounts-server=https://accounts.zoho.in",
                follow_redirects=False
            )
            # Should redirect back to frontend home success page
            assert res.status_code == 307
            assert "connection=success" in res.headers["location"]
            
            # Verify database entry has scopes
            db = TestingSession()
            cred = db.query(models.ZohoCredential).first()
            assert cred is not None
            assert cred.scopes == "ZohoExpense.expense.CREATE ZohoExpense.expensereport.READ"
            assert cred.organization_name == "Callback Org"
            assert cred.organization_id == "org-777"
            db.close()
            
    app.dependency_overrides.clear()

def test_sensitive_logging_filter():
    """Verifies that SensitiveDataFilter censors sensitive fields in log messages and record arguments."""
    from app.main import SensitiveDataFilter
    import logging
    
    filt = SensitiveDataFilter()
    
    # 1. Test message sanitization
    record1 = logging.LogRecord(
        name="test", level=logging.INFO, pathname="", lineno=0,
        msg="Received code=12345&client_secret=abcxyz for OAuth exchange.",
        args=(), exc_info=None
    )
    assert filt.filter(record1)
    assert "code=[REDACTED]" in record1.msg
    assert "client_secret=[REDACTED]" in record1.msg
    assert "12345" not in record1.msg
    assert "abcxyz" not in record1.msg
    
    # 2. Test record arguments sanitization (like uvicorn access logs)
    record2 = logging.LogRecord(
        name="test", level=logging.INFO, pathname="", lineno=0,
        msg="GET %s HTTP/1.1",
        args=("/api/zoho/callback?code=somecode123&state=abc",), exc_info=None
    )
    assert filt.filter(record2)
    assert "code=[REDACTED]" in record2.args[0]
    assert "somecode123" not in record2.args[0]
    
    # 3. Test Authorization header sanitization
    record3 = logging.LogRecord(
        name="test", level=logging.INFO, pathname="", lineno=0,
        msg="Sending request with Authorization: Bearer secret-token-abc",
        args=(), exc_info=None
    )
    assert filt.filter(record3)
    assert "Authorization: [REDACTED]" in record3.msg
    assert "secret-token-abc" not in record3.msg

