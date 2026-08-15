import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../backend')))

import datetime
import io
from unittest.mock import patch, MagicMock
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient
import openpyxl

from app.database.session import Base
from app.database import models
from app.services.zoho.client import ZohoOAuthService, ZohoExpenseClient, ZohoEntityResolver
from app.services.zoho.bulk_processor import run_bulk_create_task
from app.security import encryption
from app.main import app

TEST_DATABASE_URL = "sqlite:///./test_bulk_temp.db"
engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@pytest.fixture(scope="function")
def db_session():
    # Setup test database tables
    Base.metadata.create_all(bind=engine)
    
    # Run manual migrations on test db
    from app.database.migrations import run_migrations
    run_migrations(engine)
    
    db = TestingSessionLocal()
    yield db
    db.close()
    Base.metadata.drop_all(bind=engine)
    engine.dispose()
    if os.path.exists("./test_bulk_temp.db"):
        try:
            os.remove("./test_bulk_temp.db")
        except Exception:
            pass

@pytest.fixture(scope="function")
def test_client(db_session):
    from app.database.session import get_db
    app.dependency_overrides[get_db] = lambda: db_session
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


def test_bulk_create_routing_and_duplicates(db_session):
    """Verifies that GST and NON_GST rows route to separate reports, and duplicates are preserved."""
    # Setup credentials
    cred = models.ZohoCredential(
        api_domain="https://www.zohoapis.com",
        encrypted_access_token=encryption.encrypt_token("access_tok"),
        encrypted_refresh_token=encryption.encrypt_token("refresh_tok"),
        expires_at=datetime.datetime.utcnow() + datetime.timedelta(hours=1),
        organization_id="12345",
        scopes="ZohoExpense.expense.CREATE"
    )
    db_session.add(cred)
    
    # Setup upload session
    session = models.UploadSession(
        file_name="test_bulk.xlsx",
        total_rows=3,
        valid_rows=3,
        invalid_rows=0,
        status="Validated"
    )
    db_session.add(session)
    db_session.commit()
    db_session.refresh(session)
    
    # Setup 3 records, where Row 2 & Row 3 are duplicate rows
    rec1 = models.ExpenseRecord(
        session_id=session.id,
        original_row_number=2,
        expense_date="2026-08-01",
        amount=100.0,
        description="Duplicate expense",
        gst_type="GST",
        category="Meals",
        paid_through="Petty Cash",
        status="VALID"
    )
    rec2 = models.ExpenseRecord(
        session_id=session.id,
        original_row_number=3,
        expense_date="2026-08-01",
        amount=100.0,
        description="Duplicate expense",
        gst_type="GST",
        category="Meals",
        paid_through="Petty Cash",
        status="VALID"
    )
    rec3 = models.ExpenseRecord(
        session_id=session.id,
        original_row_number=4,
        expense_date="2026-08-02",
        amount=250.0,
        description="Non-GST expense",
        gst_type="NON_GST",
        category="Travel",
        paid_through="Petty Cash",
        status="VALID"
    )
    db_session.add_all([rec1, rec2, rec3])
    db_session.commit()

    # Mock resolvers and Zoho API post
    with patch("app.services.zoho.bulk_processor.ZohoEntityResolver.resolve_category", return_value="cat_123"), \
         patch("app.services.zoho.bulk_processor.ZohoEntityResolver.resolve_paid_through", return_value="pt_456"), \
         patch("app.services.zoho.bulk_processor.ZohoExpenseClient.create_expense") as mock_create_expense, \
         patch("app.services.zoho.bulk_processor.ZohoExpenseClient.get_report_details", return_value={"report_name": "Test Report"}):
         
        # Mock Zoho creation returns separate IDs
        mock_create_expense.side_effect = [
            {"expense_id": "zoho_exp_1"},
            {"expense_id": "zoho_exp_2"},
            {"expense_id": "zoho_exp_3"}
        ]
        
        # Execute background task code directly for testing
        run_bulk_create_task(
            session_id=session.id,
            gst_report_id="gst_rep_id",
            nongst_report_id="nongst_rep_id",
            skip_invalid=False,
            db=db_session
        )
        
        # Assertions
        db_session.refresh(session)
        assert session.status == "Completed"
        
        db_records = db_session.query(models.ExpenseRecord).filter(models.ExpenseRecord.session_id == session.id).all()
        assert len(db_records) == 3
        
        # Check duplicate rows created as separate expenses
        assert db_records[0].zoho_status == "CREATED"
        assert db_records[0].zoho_expense_id == "zoho_exp_1"
        assert db_records[0].destination_report_id == "gst_rep_id"
        
        assert db_records[1].zoho_status == "CREATED"
        assert db_records[1].zoho_expense_id == "zoho_exp_2"
        assert db_records[1].destination_report_id == "gst_rep_id"
        
        # Check routing of GST/NON_GST
        assert db_records[2].zoho_status == "CREATED"
        assert db_records[2].zoho_expense_id == "zoho_exp_3"
        assert db_records[2].destination_report_id == "nongst_rep_id"


def test_bulk_create_idempotency_resumable(db_session):
    """Verifies that bulk creation skips already created rows and continues processing failed ones."""
    cred = models.ZohoCredential(
        api_domain="https://www.zohoapis.com",
        encrypted_access_token=encryption.encrypt_token("access_tok"),
        encrypted_refresh_token=encryption.encrypt_token("refresh_tok"),
        expires_at=datetime.datetime.utcnow() + datetime.timedelta(hours=1),
        organization_id="12345"
    )
    db_session.add(cred)
    
    session = models.UploadSession(
        file_name="test_bulk_resumable.xlsx",
        total_rows=3,
        valid_rows=3,
        invalid_rows=0,
        status="Validated"
    )
    db_session.add(session)
    db_session.commit()
    db_session.refresh(session)
    
    # Record 1: Already created. Record 2: Failed. Record 3: Pending.
    rec1 = models.ExpenseRecord(
        session_id=session.id,
        original_row_number=2,
        expense_date="2026-08-01",
        amount=100.0,
        description="Already created row",
        gst_type="GST",
        category="Meals",
        paid_through="Petty Cash",
        status="VALID",
        zoho_status="CREATED",
        zoho_expense_id="zoho_exp_existing"
    )
    rec2 = models.ExpenseRecord(
        session_id=session.id,
        original_row_number=3,
        expense_date="2026-08-02",
        amount=120.0,
        description="Previously failed row",
        gst_type="GST",
        category="Meals",
        paid_through="Petty Cash",
        status="VALID",
        zoho_status="FAILED",
        zoho_error="Network timeout"
    )
    rec3 = models.ExpenseRecord(
        session_id=session.id,
        original_row_number=4,
        expense_date="2026-08-03",
        amount=140.0,
        description="Pending row",
        gst_type="GST",
        category="Meals",
        paid_through="Petty Cash",
        status="VALID",
        zoho_status="PENDING"
    )
    db_session.add_all([rec1, rec2, rec3])
    db_session.commit()

    with patch("app.services.zoho.bulk_processor.ZohoEntityResolver.resolve_category", return_value="cat_123"), \
         patch("app.services.zoho.bulk_processor.ZohoEntityResolver.resolve_paid_through", return_value="pt_456"), \
         patch("app.services.zoho.bulk_processor.ZohoExpenseClient.create_expense") as mock_create_expense, \
         patch("app.services.zoho.bulk_processor.ZohoExpenseClient.get_report_details", return_value={"report_name": "Test Report"}):
         
        # Mock Zoho creation returns IDs for Row 3 and Row 4
        mock_create_expense.side_effect = [
            {"expense_id": "zoho_exp_retry_success"},
            {"expense_id": "zoho_exp_new_success"}
        ]
        
        # When triggering bulk creation, the API endpoint resets FAILED rows to PENDING. Let's simulate that:
        db_session.query(models.ExpenseRecord).filter(
            models.ExpenseRecord.session_id == session.id,
            models.ExpenseRecord.zoho_status.in_(["FAILED", "CANCELLED"])
        ).update({"zoho_status": "PENDING", "zoho_error": None})
        db_session.commit()
        
        run_bulk_create_task(
            session_id=session.id,
            gst_report_id="gst_rep_id",
            nongst_report_id="nongst_rep_id",
            skip_invalid=False,
            db=db_session
        )
        
        # Refresh and verify
        db_session.refresh(rec1)
        db_session.refresh(rec2)
        db_session.refresh(rec3)
        
        # Rec 1 must remain untouched (idempotent safety check)
        assert rec1.zoho_status == "CREATED"
        assert rec1.zoho_expense_id == "zoho_exp_existing"
        
        # Rec 2 should be successfully retried
        assert rec2.zoho_status == "CREATED"
        assert rec2.zoho_expense_id == "zoho_exp_retry_success"
        
        # Rec 3 should be successfully created
        assert rec3.zoho_status == "CREATED"
        assert rec3.zoho_expense_id == "zoho_exp_new_success"
        
        # create_expense should have been called only twice (for rec2 and rec3), not for rec1.
        assert mock_create_expense.call_count == 2


def test_bulk_create_api_rate_limiting_429(db_session):
    """Verifies that 429 rate limit errors trigger exponential backoff retry logic."""
    cred = models.ZohoCredential(
        api_domain="https://www.zohoapis.com",
        encrypted_access_token=encryption.encrypt_token("access_tok"),
        encrypted_refresh_token=encryption.encrypt_token("refresh_tok"),
        expires_at=datetime.datetime.utcnow() + datetime.timedelta(hours=1),
        organization_id="12345"
    )
    db_session.add(cred)
    db_session.commit()
    
    # Mock httpx response containing 429 followed by 201
    mock_response_429 = MagicMock()
    mock_response_429.status_code = 429
    mock_response_429.headers = {"Retry-After": "1"}
    
    mock_response_201 = MagicMock()
    mock_response_201.status_code = 201
    mock_response_201.json.return_value = {"expense": {"expense_id": "zoho_exp_after_429"}}
    
    with patch("httpx.post") as mock_post, \
         patch("time.sleep") as mock_sleep:
         
        # Simulate rate limit hit once, then success
        mock_post.side_effect = [mock_response_429, mock_response_201]
        
        payload = {"date": "2026-08-01", "amount": 50.0, "category_id": "cat_1"}
        res = ZohoExpenseClient.create_expense(db_session, payload)
        
        assert res.get("expense_id") == "zoho_exp_after_429"
        # Sleep should be called for the retry backoff
        mock_sleep.assert_called_with(1.0)
        assert mock_post.call_count == 2


def test_error_report_endpoint(test_client, db_session):
    """Verifies that the error report endpoint generates a valid spreadsheet with failed rows."""
    session = models.UploadSession(
        file_name="test_err_rep.xlsx",
        total_rows=3,
        valid_rows=2,
        invalid_rows=1,
        status="Errors"
    )
    db_session.add(session)
    db_session.commit()
    db_session.refresh(session)
    
    # Create one failed row
    rec = models.ExpenseRecord(
        session_id=session.id,
        original_row_number=3,
        expense_date="2026-08-02",
        amount=120.0,
        description="Failed expense row",
        gst_type="GST",
        category="Meals",
        paid_through="Petty Cash",
        status="VALID",
        zoho_status="FAILED",
        zoho_error="Invalid category selected",
        destination_report_id="rep_987"
    )
    db_session.add(rec)
    
    # Create audit log entry for the failure
    audit = models.ZohoAuditLog(
        session_id=session.id,
        excel_row=3,
        amount=120.0,
        description="Failed expense row",
        destination_report="August 2026 - GST",
        result="FAILED",
        error_details="Invalid category selected"
    )
    db_session.add(audit)
    db_session.commit()
    
    # Trigger download
    response = test_client.get(f"/api/zoho/sessions/{session.id}/error-report")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    
    # Load downloaded workbook
    wb = openpyxl.load_workbook(io.BytesIO(response.content))
    ws = wb.active
    assert ws.title == "Failed Expenses"
    
    # Validate headers
    headers = [cell.value for cell in ws[1]]
    assert "Excel Row" in headers
    assert "Failure Reason" in headers
    assert "Destination Report" in headers
    
    # Validate data details
    row2_vals = [cell.value for cell in ws[2]]
    assert 3 in row2_vals # original row number
    assert 120.0 in row2_vals # amount
    assert "FAILED" in row2_vals # zoho status
    assert "Invalid category selected" in row2_vals # failure reason
    assert "August 2026 - GST" in row2_vals # destination report name


def test_lock_endpoints(test_client):
    """Verifies that the lock API endpoints set, verify, and disable PINs successfully."""
    # Initially status has_pin should be False
    res = test_client.get("/api/lock/status")
    assert res.status_code == 200
    assert res.json() == {"has_pin": False}
    
    # Try verifying when not set (should pass verified=True since no PIN restricts access)
    res = test_client.post("/api/lock/verify", json={"pin": "1234"})
    assert res.status_code == 200
    assert res.json() == {"verified": True}
    
    # Setup PIN
    res = test_client.post("/api/lock/setup", json={"pin": "1234"})
    assert res.status_code == 200
    assert res.json() == {"status": "success", "message": "PIN setup successful."}
    
    # Check status again
    res = test_client.get("/api/lock/status")
    assert res.json() == {"has_pin": True}
    
    # Verify correct PIN
    res = test_client.post("/api/lock/verify", json={"pin": "1234"})
    assert res.status_code == 200
    assert res.json() == {"verified": True}
    
    # Verify incorrect PIN
    res = test_client.post("/api/lock/verify", json={"pin": "9999"})
    assert res.status_code == 400
    assert res.json()["detail"] == "Incorrect PIN."
    
    # Disable PIN with incorrect PIN
    res = test_client.post("/api/lock/disable", json={"pin": "9999"})
    assert res.status_code == 400
    
    # Disable PIN with correct PIN
    res = test_client.post("/api/lock/disable", json={"pin": "1234"})
    assert res.status_code == 200
    assert res.json() == {"status": "success", "message": "PIN disabled."}
    
    # Status has_pin should be False again
    res = test_client.get("/api/lock/status")
    assert res.json() == {"has_pin": False}


def test_dry_run_endpoint(test_client, db_session):
    """Verifies that the dry-run check handles validation of destination reports and calculates stats."""
    # Setup session
    session = models.UploadSession(
        file_name="test_dry.xlsx",
        total_rows=10,
        valid_rows=8,
        invalid_rows=2,
        gst_count=5,
        nongst_count=3,
        status="Validated"
    )
    db_session.add(session)
    db_session.commit()
    db_session.refresh(session)
    
    # Setup record
    rec = models.ExpenseRecord(
        session_id=session.id,
        original_row_number=2,
        expense_date="2026-08-01",
        amount=100.0,
        gst_type="GST",
        status="VALID",
        zoho_status="PENDING"
    )
    db_session.add(rec)
    db_session.commit()
    
    # Setup credentials
    cred = models.ZohoCredential(
        api_domain="https://www.zohoapis.com",
        encrypted_access_token=encryption.encrypt_token("access_tok"),
        encrypted_refresh_token=encryption.encrypt_token("refresh_tok"),
        expires_at=datetime.datetime.utcnow() + datetime.timedelta(hours=1),
        organization_id="12345"
    )
    db_session.add(cred)
    db_session.commit()
    
    # Mock get_report_details
    with patch("app.services.zoho.client.ZohoExpenseClient.get_report_details") as mock_get_report:
        mock_get_report.side_effect = lambda db, report_id: {"name": "GST Report" if report_id == "gst_1" else "NON-GST Report"}
        
        response = test_client.post("/api/zoho/expenses/dry-run", json={
            "session_id": session.id,
            "gst_report_id": "gst_1",
            "nongst_report_id": "nongst_2"
        })
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["excel_rows"] == 10
        assert data["valid_rows"] == 8
        assert data["invalid_rows"] == 2
        assert data["gst_rows"] == 5
        assert data["nongst_rows"] == 3
        assert data["gst_report_name"] == "GST Report"
        assert data["would_create"] == 1
        assert data["changes_made"] == 0


def test_sequential_upload_session_id_prefix(db_session):
    """Verifies sequence UP-YYYYMMDD-001, UP-YYYYMMDD-002 prefixes are computed sequentially."""
    from app.services.upload.history_service import create_upload_session
    
    session1 = create_upload_session(db_session, "test1.xlsx", 5, 4, 1, 3, 1, "VALIDATING")
    session2 = create_upload_session(db_session, "test2.xlsx", 5, 4, 1, 3, 1, "VALIDATING")
    
    today_str = datetime.date.today().strftime("%Y%m%d")
    assert session1.upload_session_id == f"UP-{today_str}-001"
    assert session2.upload_session_id == f"UP-{today_str}-002"
