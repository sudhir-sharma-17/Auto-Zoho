import datetime
import httpx
import logging
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from app.database import models
from app.services.zoho.client import ZohoExpenseClient

logger = logging.getLogger(__name__)

class ZohoMasterDataService:
    # 5-minute in-memory cache
    # Structure: { "data": [...], "timestamp": datetime.datetime }
    _cache = {}
    CACHE_DURATION_SECONDS = 300
    
    @classmethod
    def clear_cache(cls):
        cls._cache = {}
        logger.info("Zoho master data cache cleared.")

    @classmethod
    def _get_paginated_data(cls, db: Session, endpoint: str, list_key: str) -> List[Dict[str, Any]]:
        now = datetime.datetime.utcnow()
        cache_key = f"{endpoint}:{list_key}"
        if cache_key in cls._cache:
            cache_entry = cls._cache[cache_key]
            elapsed = (now - cache_entry["timestamp"]).total_seconds()
            if elapsed < cls.CACHE_DURATION_SECONDS:
                return cache_entry["data"]
                
        headers, api_domain = ZohoExpenseClient.get_auth_headers(db)
        
        page = 1
        all_items = []
        
        while True:
            # Check if there is already a query param in endpoint
            separator = "&" if "?" in endpoint else "?"
            url = f"{api_domain.rstrip('/')}{endpoint}{separator}page={page}&per_page=200"
            
            logger.info(f"Fetching master data from Zoho: {url}")
            res = httpx.get(url, headers=headers, timeout=15.0)
            if res.status_code != 200:
                logger.error(f"Failed to fetch master data from {url}: {res.text}")
                raise ValueError(f"Zoho master data fetch failed: {res.text}")
                
            data = res.json()
            items = data.get(list_key, [])
            
            # Fallback handling for categories
            if not items and list_key == "expense_accounts":
                items = data.get("expense_categories") or data.get("expensereports") or []
                
            all_items.extend(items)
            
            # Check page context for has_more_page
            page_context = data.get("page_context", {})
            has_more = page_context.get("has_more_page", False)
            if not has_more:
                break
                
            page += 1
            
        cls._cache[cache_key] = {
            "data": all_items,
            "timestamp": now
        }
        return all_items

    @classmethod
    def get_categories(cls, db: Session) -> List[Dict[str, Any]]:
        # In Zoho expense categories are returned as expense_accounts
        items = cls._get_paginated_data(db, "/expense/v1/expensecategories", "expense_accounts")
        return [
            {
                "id": cat.get("category_id"),
                "name": cat.get("category_name") or cat.get("name"),
                "parent_name": cat.get("parent_account_name") or None,
                "status": cat.get("status") or "active",
                "is_enabled": cat.get("is_enabled", True)
            }
            for cat in items
        ]

    @classmethod
    def get_projects(cls, db: Session) -> List[Dict[str, Any]]:
        items = cls._get_paginated_data(db, "/expense/v1/projects", "projects")
        return [
            {
                "id": proj.get("project_id"),
                "name": proj.get("project_name"),
                "status": proj.get("status") or "active"
            }
            for proj in items
        ]

    @classmethod
    def get_vendors(cls, db: Session) -> List[Dict[str, Any]]:
        items = cls._get_paginated_data(db, "/expense/v1/contacts?contact_type=vendor", "contacts")
        return [
            {
                "id": vendor.get("contact_name"),  # Merchant is a string field
                "name": vendor.get("contact_name"),
                "status": vendor.get("status") or "active"
            }
            for vendor in items
        ]

    @classmethod
    def get_taxes(cls, db: Session) -> List[Dict[str, Any]]:
        fallback = [{"id": "none", "name": "No Tax / Exempt (Ignore)", "status": "active"}]
        try:
            items = cls._get_paginated_data(db, "/expense/v1/settings/taxes", "taxes")
            api_taxes = [
                {
                    "id": str(tax.get("tax_id")),
                    "name": tax.get("tax_name"),
                    "status": tax.get("status") or "active"
                }
                for tax in items
            ]
            return fallback + api_taxes
        except Exception as e:
            logger.warning(f"Failed to fetch taxes from Zoho: {e}. Returning fallback list.")
            return fallback

    @classmethod
    def get_payment_modes(cls, db: Session) -> List[Dict[str, Any]]:
        return [
            {"id": "668650000000000459", "name": "Petty Cash"},
            {"id": "668650000000904009", "name": "07. RBL Bank-Manoj"},
            {"id": "668650000000000573", "name": "Employee Reimbursements"}
        ]

    @classmethod
    def get_expense_kinds(cls, db: Session) -> List[Dict[str, Any]]:
        return [
            {"id": "668650000004152043", "name": "Corporate Overhead Expense_v1"},
            {"id": "668650000004152045", "name": "Project Expense_v1"}
        ]

    @classmethod
    def get_gst_options(cls, db: Session) -> List[Dict[str, Any]]:
        return [
            {"id": "668650000004152055", "name": "GST"},
            {"id": "668650000004152057", "name": "Non-GST"}
        ]

    @classmethod
    def get_base_currency(cls, db: Session) -> str:
        cache_key = "base_currency_id"
        now = datetime.datetime.utcnow()
        if cache_key in cls._cache:
            cache_entry = cls._cache[cache_key]
            elapsed = (now - cache_entry["timestamp"]).total_seconds()
            if elapsed < cls.CACHE_DURATION_SECONDS:
                return cache_entry["data"]
                
        currency_id = "668650000000000064" # Standard fallback for INR
        try:
            headers, api_domain = ZohoExpenseClient.get_auth_headers(db)
            url = f"{api_domain.rstrip('/')}/expense/v1/organizations"
            res = httpx.get(url, headers=headers, timeout=10.0)
            if res.status_code == 200:
                data = res.json()
                orgs = data.get("organizations", [])
                cred = db.query(models.ZohoCredential).first()
                target_id = cred.organization_id if cred else None
                
                for org in orgs:
                    if str(org.get("organization_id")) == str(target_id) or not target_id:
                        code = org.get("currency_id")
                        if code:
                            currency_id = str(code)
                            break
        except Exception as e:
            logger.warning(f"Failed to fetch base currency from organizations API: {e}. Defaulting to fallback.")
            
        cls._cache[cache_key] = {
            "data": currency_id,
            "timestamp": now
        }
        return currency_id
