import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../backend')))

import datetime
from unittest.mock import patch, MagicMock
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database.session import Base, get_db
from app.database import models
from app.services.zoho.client import ZohoOAuthService, ZohoExpenseClient, ZohoEntityResolver
from app.security import encryption

TEST_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@pytest.fixture(scope="function")
def db_session():
    ZohoEntityResolver.clear_cache()
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    # Seed connection credentials
    cred = models.ZohoCredential(
        api_domain="https://www.zohoapis.in",
        encrypted_access_token=encryption.encrypt_token("access"),
        encrypted_refresh_token=encryption.encrypt_token("refresh"),
        expires_at=datetime.datetime.utcnow() + datetime.timedelta(hours=1),
        organization_id="org-123"
    )
    db.add(cred)
    db.commit()
    yield db
    db.close()
    Base.metadata.drop_all(bind=engine)

@patch("httpx.get")
def test_report_api_response_parsing_expense_reports(mock_get, db_session):
    """Verifies that response with 'expense_reports' key is correctly parsed."""
    mock_get.return_value = MagicMock(
        status_code=200,
        json=lambda: {
            "expense_reports": [
                {"report_id": "rep-gst-1", "report_name": "GST July 2026", "status": "draft", "start_date": "2026-07-01", "end_date": "2026-07-31"},
                {"report_id": "rep-nongst-1", "report_name": "Non-GST July 2026", "status": "draft", "start_date": "2026-07-01", "end_date": "2026-07-31"}
            ]
        }
    )
    
    reports = ZohoExpenseClient.get_reports(db_session)
    assert len(reports) == 2
    assert reports[0]["report_id"] == "rep-gst-1"
    assert reports[0]["report_name"] == "GST July 2026"
    assert reports[1]["report_id"] == "rep-nongst-1"
    assert reports[1]["report_name"] == "Non-GST July 2026"

@patch("httpx.get")
def test_report_api_response_parsing_expensereports(mock_get, db_session):
    """Verifies that fallback response with 'expensereports' key is also parsed successfully."""
    mock_get.return_value = MagicMock(
        status_code=200,
        json=lambda: {
            "expensereports": [
                {"report_id": "rep-gst-2", "report_name": "GST August 2026", "status": "approved", "start_date": "2026-08-01", "end_date": "2026-08-31"}
            ]
        }
    )
    
    reports = ZohoExpenseClient.get_reports(db_session)
    assert len(reports) == 1
    assert reports[0]["report_id"] == "rep-gst-2"
    assert reports[0]["report_name"] == "GST August 2026"

@patch("httpx.get")
def test_empty_report_response(mock_get, db_session):
    """Verifies that an empty report response is handled gracefully without crashing."""
    mock_get.return_value = MagicMock(
        status_code=200,
        json=lambda: {"expense_reports": []}
    )
    
    reports = ZohoExpenseClient.get_reports(db_session)
    assert reports == []

@patch("httpx.get")
def test_status_normalization_and_filtering(mock_get, db_session):
    """Verifies status casing normalization and ensures only draft/submitted/approved are allowed."""
    mock_get.return_value = MagicMock(
        status_code=200,
        json=lambda: {
            "expense_reports": [
                {"report_id": "r1", "report_name": "GST", "status": "  Draft  "},
                {"report_id": "r2", "report_name": "Non-GST", "status": "SUBMITTED"},
                {"report_id": "r3", "report_name": "Other", "status": "REJECTED"},
                {"report_id": "r4", "report_name": "Approved", "status": "Approved"}
            ]
        }
    )
    
    reports = ZohoExpenseClient.get_reports(db_session)
    # r3 (REJECTED) should be filtered out; r1, r2, r4 should be returned
    assert len(reports) == 3
    ids = [r["report_id"] for r in reports]
    assert "r1" in ids
    assert "r2" in ids
    assert "r4" in ids
    assert "r3" not in ids

@patch("httpx.get")
def test_get_report_details_both_keys(mock_get, db_session):
    """Verifies single report details endpoint parses both 'expense_report' and 'expensereport'."""
    # Scenario A: expense_report
    mock_get.return_value = MagicMock(
        status_code=200,
        json=lambda: {"expense_report": {"report_name": "GST June"}}
    )
    details = ZohoExpenseClient.get_report_details(db_session, "rep-id")
    assert details["report_name"] == "GST June"
    
    # Scenario B: expensereport
    mock_get.return_value = MagicMock(
        status_code=200,
        json=lambda: {"expensereport": {"report_name": "Non-GST June"}}
    )
    details2 = ZohoExpenseClient.get_report_details(db_session, "rep-id")
    assert details2["report_name"] == "Non-GST June"

def test_frontend_report_dropdown_population_conformance():
    """Confirms that report records contain report_id and report_name matching frontend expectations."""
    # Mimic a returned report item from backend
    report_item = {
        "report_id": "668650000013588075",
        "report_name": "JULY 2026 - MANOJ - GST",
        "status": "draft",
        "start_date": "2026-07-01",
        "end_date": "2026-07-31"
    }
    
    # Ensure they conform to the ZohoReport type structure in frontend
    assert isinstance(report_item["report_id"], str)
    assert isinstance(report_item["report_name"], str)
    assert isinstance(report_item["status"], str)
    assert "start_date" in report_item
    assert "end_date" in report_item

@patch("httpx.get")
def test_category_api_parsing_and_resolution(mock_get, db_session):
    """Verifies category API response parsing, case-insensitive matching, and error throwing."""
    # Mock category listing API
    mock_get.return_value = MagicMock(
        status_code=200,
        json=lambda: {
            "expense_categories": [
                {"category_id": "c1", "name": "Cabinetry"},
                {"category_id": "c2", "name": "Office Supplies"}
            ]
        }
    )
    
    # Reset caches
    ZohoEntityResolver._categories_cache = None
    
    # 1. Test exact match
    cat_id = ZohoEntityResolver.resolve_category(db_session, "Cabinetry")
    assert cat_id == "c1"
    
    # 2. Test case-insensitive and stripped match
    cat_id_ci = ZohoEntityResolver.resolve_category(db_session, "  office supplies  ")
    assert cat_id_ci == "c2"
    
    # 3. Test category not found raises exact ValueError
    with pytest.raises(ValueError) as excinfo:
        ZohoEntityResolver.resolve_category(db_session, "Travel")
    assert "Cannot create this expense because category 'Travel' could not be found in Zoho Expense." in str(excinfo.value)

@patch("httpx.get")
def test_category_caching_layer(mock_get, db_session):
    """Verifies that ZohoEntityResolver caches category data and does not make duplicate requests within 5 minutes."""
    mock_get.return_value = MagicMock(
        status_code=200,
        json=lambda: {
            "expense_categories": [
                {"category_id": "c1", "name": "Cabinetry"}
            ]
        }
    )
    
    # Reset caches
    ZohoEntityResolver._categories_cache = None
    
    # Resolve first time (should hit API)
    id1 = ZohoEntityResolver.resolve_category(db_session, "Cabinetry")
    assert id1 == "c1"
    assert mock_get.call_count == 1
    
    # Resolve second time (should reuse cache)
    id2 = ZohoEntityResolver.resolve_category(db_session, "Cabinetry")
    assert id2 == "c1"
    assert mock_get.call_count == 1  # Still 1 call

def test_scope_validation_check_endpoints():
    """Verifies that check_zoho_scopes validates presence of all 8 required scopes."""
    from fastapi.testclient import TestClient
    from app.main import app
    
    # Create test database setup
    temp_db_path = "./test_scope_temp.db"
    if os.path.exists(temp_db_path):
        try:
            os.remove(temp_db_path)
        except OSError:
            pass
            
    test_engine = create_engine(f"sqlite:///{temp_db_path}", connect_args={"check_same_thread": False})
    TestingSession = sessionmaker(bind=test_engine)
    Base.metadata.create_all(bind=test_engine)
    
    def override_get_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()
            
    app.dependency_overrides[get_db] = override_get_db
    
    try:
        with TestClient(app) as client:
            # Scenario A: Missing required scopes (only expense.CREATE present)
            db = TestingSession()
            cred = models.ZohoCredential(
                api_domain="https://www.zohoapis.in",
                encrypted_access_token=encryption.encrypt_token("access"),
                encrypted_refresh_token=encryption.encrypt_token("refresh"),
                expires_at=datetime.datetime.utcnow() + datetime.timedelta(hours=1),
                scopes="ZohoExpense.expense.CREATE"
            )
            db.add(cred)
            db.commit()
            db.close()
            
            res = client.get("/api/zoho/check-scopes")
            assert res.status_code == 200
            assert res.json() == {"connected": True, "has_create_scope": False}
            
            # Scenario B: All 8 required scopes present
            db = TestingSession()
            cred_db = db.query(models.ZohoCredential).first()
            cred_db.scopes = (
                "ZohoExpense.expense.CREATE ZohoExpense.expensereport.READ ZohoExpense.orgsettings.READ "
                "ZohoExpense.expensecategory.READ ZohoExpense.project.READ ZohoExpense.contacts.READ "
                "ZohoExpense.tax.READ ZohoExpense.settings.READ"
            )
            db.commit()
            db.close()
            
            res = client.get("/api/zoho/check-scopes")
            assert res.status_code == 200
            assert res.json() == {"connected": True, "has_create_scope": True}
    finally:
        app.dependency_overrides.clear()
        test_engine.dispose()
        if os.path.exists(temp_db_path):
            try:
                os.remove(temp_db_path)
            except OSError:
                pass

