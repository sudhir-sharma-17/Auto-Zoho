import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../backend')))

import datetime
from unittest.mock import patch, MagicMock
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

from app.database.session import Base
from app.database import models
from app.services.zoho.client import ZohoOAuthService, ZohoExpenseClient, ZohoEntityResolver
from app.security import encryption
from app.main import app

TEST_DATABASE_URL = "sqlite:///./test_create_temp.db"
engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@pytest.fixture(scope="function")
def db_session():
    # Reset Entity Resolver caches before each test
    ZohoEntityResolver.clear_cache()
    # Setup test database tables
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    yield db
    db.close()
    Base.metadata.drop_all(bind=engine)
    engine.dispose()
    if os.path.exists("./test_create_temp.db"):
        try:
            os.remove("./test_create_temp.db")
        except Exception:
            pass

@pytest.fixture(scope="function")
def test_client(db_session):
    from app.database.session import get_db
    from app.api.deps import get_current_admin
    # Override dependencies
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_current_admin] = lambda: models.AdminAuth(
        id=1,
        username="admin",
        email="admin@example.com",
        password_initialized=True
    )
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


def test_scopes_validation(db_session):
    """Verifies scopes check accurately identifies missing CREATE permissions."""
    # Scenario A: Stored scopes do not have CREATE
    cred1 = models.ZohoCredential(
        api_domain="https://www.zohoapis.com",
        encrypted_access_token=encryption.encrypt_token("access"),
        encrypted_refresh_token=encryption.encrypt_token("refresh"),
        expires_at=datetime.datetime.utcnow() + datetime.timedelta(hours=1),
        scopes="ZohoExpense.expensereport.READ ZohoExpense.orgsettings.READ"
    )
    db_session.add(cred1)
    db_session.commit()
    
    # Verify scopes check returns False for CREATE scope
    scopes_str1 = cred1.scopes or ""
    scopes_list1 = [s.strip() for s in scopes_str1.replace(",", " ").split(" ") if s.strip()]
    assert "ZohoExpense.expense.CREATE" not in scopes_list1
    
    # Scenario B: Stored scopes have CREATE
    cred1.scopes = "ZohoExpense.expensereport.READ ZohoExpense.expense.CREATE ZohoExpense.orgsettings.READ"
    db_session.commit()
    
    scopes_str2 = cred1.scopes or ""
    scopes_list2 = [s.strip() for s in scopes_str2.replace(",", " ").split(" ") if s.strip()]
    assert "ZohoExpense.expense.CREATE" in scopes_list2


@patch("httpx.get")
def test_entity_resolver_category(mock_get, db_session):
    """Verifies categories match case-insensitively and returns IDs."""
    # Seed connection credentials
    cred = models.ZohoCredential(
        api_domain="https://www.zohoapis.com",
        encrypted_access_token=encryption.encrypt_token("access"),
        encrypted_refresh_token=encryption.encrypt_token("refresh"),
        expires_at=datetime.datetime.utcnow() + datetime.timedelta(hours=1)
    )
    db_session.add(cred)
    db_session.commit()
    
    mock_get.return_value = MagicMock(
        status_code=200,
        json=lambda: {
            "expense_categories": [
                {"category_id": "cat-001", "name": "Manufactured Cabinetry_v1"},
                {"category_id": "cat-002", "name": "Travel"}
            ]
        }
    )
    
    # Exact case match
    cat_id = ZohoEntityResolver.resolve_category(db_session, "Manufactured Cabinetry_v1")
    assert cat_id == "cat-001"
    
    # Case-insensitive match
    cat_id_ci = ZohoEntityResolver.resolve_category(db_session, "manufactured cabinetry_v1")
    assert cat_id_ci == "cat-001"
    
    # Unmatched category throws ValueError
    with pytest.raises(ValueError) as excinfo:
        ZohoEntityResolver.resolve_category(db_session, "Unknown Category")
    assert "Cannot create this expense because category 'Unknown Category' could not be found in Zoho Expense." in str(excinfo.value)


@patch("httpx.get")
def test_entity_resolver_vendor_rules(mock_get, db_session):
    """Verifies that unmatched vendor names raise the exact ValueError requested."""
    # Seed credentials
    cred = models.ZohoCredential(
        api_domain="https://www.zohoapis.com",
        encrypted_access_token=encryption.encrypt_token("access"),
        encrypted_refresh_token=encryption.encrypt_token("refresh"),
        expires_at=datetime.datetime.utcnow() + datetime.timedelta(hours=1)
    )
    db_session.add(cred)
    db_session.commit()
    
    # Vendor name is a free-text field in Zoho Expense.
    # It returns the input string directly without lookup or validation errors.
    vendor = ZohoEntityResolver.resolve_vendor(db_session, "abc hardware")
    assert vendor == "abc hardware"
    
    vendor2 = ZohoEntityResolver.resolve_vendor(db_session, "  XYZ Supply Co ")
    assert vendor2 == "XYZ Supply Co"


@patch("httpx.get")
def test_entity_resolver_projects_and_taxes(mock_get, db_session):
    """Tests project and tax entity resolutions."""
    cred = models.ZohoCredential(
        api_domain="https://www.zohoapis.com",
        encrypted_access_token=encryption.encrypt_token("access"),
        encrypted_refresh_token=encryption.encrypt_token("refresh"),
        expires_at=datetime.datetime.utcnow() + datetime.timedelta(hours=1)
    )
    db_session.add(cred)
    db_session.commit()
    
    # 1. Projects resolver
    mock_get.return_value = MagicMock(
        status_code=200,
        json=lambda: {
            "projects": [
                {"project_id": "proj-9", "project_name": "Project Alpha"}
            ]
        }
    )
    proj_id = ZohoEntityResolver.resolve_project(db_session, "project alpha")
    assert proj_id == "proj-9"
    
    # 2. Taxes resolver
    mock_get.return_value = MagicMock(
        status_code=200,
        json=lambda: {
            "taxes": [
                {"tax_id": "tax-18", "tax_name": "GST 18%"}
            ]
        }
    )
    tax_id = ZohoEntityResolver.resolve_tax(db_session, "gst 18%")
    assert tax_id == "tax-18"


@patch("httpx.post")
@patch("httpx.get")
def test_single_expense_creation_endpoint(mock_get, mock_post, db_session, test_client):
    """Verifies that the test creation API completes resolved postings and saves audit logs."""
    # Seed connection credentials with CREATE scope
    cred = models.ZohoCredential(
        api_domain="https://www.zohoapis.com",
        encrypted_access_token=encryption.encrypt_token("access"),
        encrypted_refresh_token=encryption.encrypt_token("refresh"),
        expires_at=datetime.datetime.utcnow() + datetime.timedelta(hours=1),
        scopes="ZohoExpense.expense.CREATE ZohoExpense.expensereport.READ"
    )
    db_session.add(cred)
    
    # Seed a local valid Excel record
    session = models.UploadSession(
        file_name="test.xlsx",
        status="Validated",
        total_rows=1,
        valid_rows=1
    )
    db_session.add(session)
    db_session.commit()
    db_session.refresh(session)
    
    record = models.ExpenseRecord(
        session_id=session.id,
        original_row_number=5,
        expense_date="2026-08-14",
        amount=210.0,
        description="Masking Tape",
        gst_type="GST",
        category="Cabinetry",
        tax_type="GST 18%",
        paid_through="07. RBL Bank-Manoj",
        project="Alpha",
        vendor_name="ABC Hardware",
        status="VALID"
    )
    db_session.add(record)
    db_session.commit()
    db_session.refresh(record)
    
    # Set up mock API endpoints for resolution and creation
    def mock_get_routes(url, *args, **kwargs):
        resp = MagicMock()
        resp.status_code = 200
        if "expensecategories" in url:
            resp.json.return_value = {"expense_categories": [{"category_id": "c1", "name": "Cabinetry"}]}
        elif "projects" in url:
            resp.json.return_value = {"projects": [{"project_id": "p1", "project_name": "Alpha"}]}
        elif "contacts" in url:
            resp.json.return_value = {"contacts": [{"contact_id": "v1", "contact_name": "ABC Hardware", "contact_type": "vendor"}]}
        elif "taxes" in url:
            resp.json.return_value = {"taxes": [{"tax_id": "t1", "tax_name": "GST 18%"}]}
        elif "expensereports" in url:
            resp.json.return_value = {"expensereport": {"report_name": "August GST Report"}}
        else:
            resp.json.return_value = {}
        return resp
        
    mock_get.side_effect = mock_get_routes
    
    mock_post_resp = MagicMock()
    mock_post_resp.status_code = 201
    mock_post_resp.json.return_value = {
        "expense": {
            "expense_id": "zoho-exp-0099"
        }
    }
    mock_post.return_value = mock_post_resp
    
    # Call POST test-create
    response = test_client.post(
        "/api/zoho/expenses/test-create",
        json={
            "record_id": record.id,
            "gst_report_id": "report-gst-111",
            "nongst_report_id": "report-nongst-222",
            "paid_through_id": "668650000000904009",
            "expense_kind_id": "668650000004152045",
            "gst_non_gst_id": "668650000004152055"
        }
    )
    
    assert response.status_code == 200
    res_data = response.json()
    assert res_data["status"] == "success"
    assert res_data["expense_id"] == "zoho-exp-0099"
    assert res_data["report_name"] == "August GST Report"
    
    # Verify mock_post was called with the mapped fields & custom fields
    assert mock_post.called
    called_json = mock_post.call_args[1]["json"]
    assert called_json["paid_through_account_id"] == "668650000000904009"
    assert called_json["payment_mode"] == "Bank Transfer"
    
    cf = called_json["custom_fields"]
    assert len(cf) == 3
    # cf[0] is vendor name
    assert cf[0]["customfield_id"] == "668650000004152025"
    assert cf[0]["value"] == "ABC Hardware"
    # cf[1] is expense kind
    assert cf[1]["customfield_id"] == "668650000004152041"
    assert cf[1]["value"] == "Project Expense_v1"
    # cf[2] is GST
    assert cf[2]["customfield_id"] == "668650000004152053"
    assert cf[2]["value"] == "GST"
    
    # Confirm local audit log record exists
    audit = db_session.query(models.ZohoAuditLog).first()
    assert audit is not None
    assert audit.result == "SUCCESS"
    assert audit.zoho_expense_id == "zoho-exp-0099"
    assert audit.excel_row == 5
    assert audit.amount == 210.0


def test_resolve_paid_through(db_session):
    """Tests paid through resolving rules and fallback prevention."""
    # Match exact
    res = ZohoEntityResolver.resolve_paid_through(db_session, "07. RBL Bank-Manoj")
    assert res == "668650000000904009"
    
    # Match clean prefix
    res2 = ZohoEntityResolver.resolve_paid_through(db_session, "RBL Bank-Manoj")
    assert res2 == "668650000000904009"
    
    # Match case insensitive and whitespace
    res3 = ZohoEntityResolver.resolve_paid_through(db_session, "  rbl bank-manoj  ")
    assert res3 == "668650000000904009"
    
    # Unmatched raises ValueError with specific string
    with pytest.raises(ValueError) as exc:
        ZohoEntityResolver.resolve_paid_through(db_session, "Axis Bank")
    assert "Cannot create this expense because Paid Through 'Axis Bank' could not be found in Zoho Expense." in str(exc.value)


def test_resolve_expense_kind(db_session):
    """Tests expense kind resolving rules."""
    res1 = ZohoEntityResolver.resolve_expense_kind(db_session, "Project Expense_v1")
    assert res1 == "668650000004152045"
    
    res2 = ZohoEntityResolver.resolve_expense_kind(db_session, "Corporate Overhead Expense_v1")
    assert res2 == "668650000004152043"
    
    with pytest.raises(ValueError) as exc:
        ZohoEntityResolver.resolve_expense_kind(db_session, "Personal Expense")
    assert "Cannot create this expense because Expense Kind 'Personal Expense' could not be found in Zoho Expense." in str(exc.value)


def test_resolve_gst_non_gst(db_session):
    """Tests GST/Non-GST option resolving rules."""
    res1 = ZohoEntityResolver.resolve_gst_non_gst(db_session, "GST")
    assert res1 == "668650000004152055"
    
    res2 = ZohoEntityResolver.resolve_gst_non_gst(db_session, "Non-GST")
    assert res2 == "668650000004152057"
    
    res3 = ZohoEntityResolver.resolve_gst_non_gst(db_session, "NON_GST")
    assert res3 == "668650000004152057"
    
    with pytest.raises(ValueError) as exc:
        ZohoEntityResolver.resolve_gst_non_gst(db_session, "Unknown_GST_Type")
    assert "Cannot create this expense because GST/Non-GST 'Unknown_GST_Type' could not be found in Zoho Expense." in str(exc.value)
