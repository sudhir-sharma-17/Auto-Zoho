import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../backend')))

import datetime
import pytest
import httpx
from unittest.mock import patch, MagicMock
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

from app.database.session import Base, get_db
from app.database import models
from app.services.zoho.master_data import ZohoMasterDataService
from app.services.zoho.client import ZohoEntityResolver
from app.security import encryption
from app.main import app

client = TestClient(app)

TEST_DATABASE_URL = "sqlite:///./test_master_temp.db"
engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@pytest.fixture(scope="function")
def db_session():
    ZohoMasterDataService.clear_cache()
    ZohoEntityResolver.clear_cache()
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    # Seed connection credentials with scopes
    cred = models.ZohoCredential(
        api_domain="https://www.zohoapis.in",
        encrypted_access_token=encryption.encrypt_token("access"),
        encrypted_refresh_token=encryption.encrypt_token("refresh"),
        expires_at=datetime.datetime.utcnow() + datetime.timedelta(hours=1),
        organization_id="org-123",
        scopes="ZohoExpense.expensereport.READ ZohoExpense.orgsettings.READ ZohoExpense.expense.CREATE ZohoExpense.expensecategory.READ ZohoExpense.project.READ ZohoExpense.contacts.READ ZohoExpense.tax.READ ZohoExpense.settings.READ"
    )
    db.add(cred)
    db.commit()
    
    # Override app get_db dependency
    def override_get_db():
        try:
            yield db
        finally:
            pass
    app.dependency_overrides[get_db] = override_get_db
    
    yield db
    
    app.dependency_overrides.clear()
    db.close()
    Base.metadata.drop_all(bind=engine)
    if os.path.exists("./test_master_temp.db"):
        try:
            os.remove("./test_master_temp.db")
        except Exception:
            pass

@pytest.fixture(autouse=True)
def clean_cache():
    ZohoMasterDataService.clear_cache()
    ZohoEntityResolver.clear_cache()

def test_master_data_payment_modes(db_session):
    modes = ZohoMasterDataService.get_payment_modes(db_session)
    assert len(modes) == 3
    assert any(m["id"] == "668650000000000459" for m in modes)
    assert any(m["id"] == "668650000000904009" for m in modes)

def test_master_data_expense_kinds(db_session):
    kinds = ZohoMasterDataService.get_expense_kinds(db_session)
    assert len(kinds) == 2
    assert kinds[0]["id"] == "668650000004152043"
    assert kinds[1]["id"] == "668650000004152045"

@patch("httpx.get")
def test_master_data_categories_pagination_and_hierarchy(mock_get, db_session):
    # Setup paginated responses
    page1_response = {
        "expense_accounts": [
            {
                "category_id": "cat_1",
                "category_name": "Manufactured Cabinetry_v1",
                "parent_account_name": "Project Cost_Interiors",
                "status": "active",
                "is_enabled": True
            }
        ],
        "page_context": {
            "page": 1,
            "per_page": 200,
            "has_more_page": True
        }
    }
    
    page2_response = {
        "expense_accounts": [
            {
                "category_id": "cat_2",
                "category_name": "Custom Hardware",
                "parent_account_name": None,
                "status": "active",
                "is_enabled": True
            }
        ],
        "page_context": {
            "page": 2,
            "per_page": 200,
            "has_more_page": False
        }
    }
    
    # Mock httpx responses sequentially
    mock_get.side_effect = [
        MagicMock(status_code=200, json=lambda: page1_response),
        MagicMock(status_code=200, json=lambda: page2_response)
    ]
    
    categories = ZohoMasterDataService.get_categories(db_session)
    
    assert len(categories) == 2
    assert categories[0]["id"] == "cat_1"
    assert categories[0]["name"] == "Manufactured Cabinetry_v1"
    assert categories[0]["parent_name"] == "Project Cost_Interiors"
    
    assert categories[1]["id"] == "cat_2"
    assert categories[1]["parent_name"] is None
    
    # Verify mock was called twice with correct pages
    assert mock_get.call_count == 2
    args1, kwargs1 = mock_get.call_args_list[0]
    assert "page=1" in args1[0]
    args2, kwargs2 = mock_get.call_args_list[1]
    assert "page=2" in args2[0]

def test_priority_matching_rules(db_session):
    from app.services.zoho.client import normalize_string
    
    # Test case 1: Exact
    assert normalize_string("Manufactured Cabinetry_v1") == "manufactured cabinetry_v1"
    
    # Test case 2: Trimmed
    assert normalize_string("  Manufactured Cabinetry_v1   ") == "manufactured cabinetry_v1"
    
    # Test case 3: Case-insensitive
    assert normalize_string("MANUFACTURED CABINETRY_V1") == "manufactured cabinetry_v1"
    
    # Test case 4: Unicode normalization (NFC vs NFD)
    nfc = "Café"
    nfd = "Cafe\u0301" # decomposed e with acute accent
    assert normalize_string(nfc) == normalize_string(nfd)
    
    # Test case 5: Whitespace normalization (multiple spaces)
    assert normalize_string("Manufactured    Cabinetry_v1") == "manufactured cabinetry_v1"

@patch("httpx.get")
def test_resolver_uses_master_data_cache(mock_get, db_session):
    # Mock categories list
    categories_response = {
        "expense_accounts": [
            {
                "category_id": "cat_1",
                "category_name": "Manufactured Cabinetry_v1",
                "status": "active",
                "is_enabled": True
            }
        ],
        "page_context": {
            "page": 1,
            "has_more_page": False
        }
    }
    mock_get.return_value = MagicMock(status_code=200, json=lambda: categories_response)
    
    # Call resolve multiple times
    res1 = ZohoEntityResolver.resolve_category(db_session, "Manufactured Cabinetry_v1")
    res2 = ZohoEntityResolver.resolve_category(db_session, "  Manufactured    Cabinetry_v1 ")
    
    assert res1 == "cat_1"
    assert res2 == "cat_1"
    
    # Verify API called only once (caching works)
    assert mock_get.call_count == 1

@patch("httpx.get")
@patch("httpx.post")
def test_create_test_expense_with_mapped_ids(mock_post, mock_get, db_session):
    # Setup session & record in db
    session = models.UploadSession(
        file_name="test.xlsx",
        status="Validated"
    )
    db_session.add(session)
    db_session.commit()
    
    record = models.ExpenseRecord(
        session_id=session.id,
        original_row_number=3,
        expense_date="2026-08-14",
        amount=1500.0,
        description="Cabinetry install",
        gst_type="GST",
        category="Manufactured Cabinetry_v1",
        paid_through="Petty Cash",
        status="VALID"
    )
    db_session.add(record)
    db_session.commit()
    
    # Mock report details fetch
    mock_get.return_value = MagicMock(status_code=200, json=lambda: {
        "expense_report": {
            "report_name": "GST Report August",
            "status": "approved"
        }
    })
    
    # Mock Zoho creation response
    mock_post.return_value = MagicMock(status_code=201, json=lambda: {
        "expense": {
            "expense_id": "zoho_exp_999"
        }
    })
    
    # Post request passing mapped category and paid_through_id explicitly
    payload = {
        "record_id": record.id,
        "gst_report_id": "rep_gst_123",
        "nongst_report_id": "rep_nongst_456",
        "category_id": "cat_mapped_999",
        "paid_through_id": "668650000000000459"
    }
    
    res = client.post("/api/zoho/expenses/test-create", json=payload)
    assert res.status_code == 200
    
    data = res.json()
    assert data["status"] == "success"
    assert data["expense_id"] == "zoho_exp_999"
    
    # Verify httpx.post was called with the explicitly mapped category_id and paid_through_account_id!
    assert mock_post.call_count == 1
    post_args, post_kwargs = mock_post.call_args
    post_data = post_kwargs.get("data") or post_kwargs.get("json") or {}
    assert post_data.get("category_id") == "cat_mapped_999"
    assert post_data.get("paid_through_account_id") == "668650000000000459"
    assert post_data.get("payment_mode") == "cash"

@patch("httpx.get")
def test_get_base_currency(mock_get, db_session):
    # Mock organizations endpoint response
    org_response = {
        "organizations": [
            {
                "organization_id": "org-123",
                "name": "Test Org",
                "currency_id": "USD"
            }
        ]
    }
    mock_get.return_value = MagicMock(status_code=200, json=lambda: org_response)
    
    currency = ZohoMasterDataService.get_base_currency(db_session)
    assert currency == "USD"
    
    # Caching works
    currency_cached = ZohoMasterDataService.get_base_currency(db_session)
    assert currency_cached == "USD"
    assert mock_get.call_count == 1
