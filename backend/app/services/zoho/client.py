import os
import httpx
import uuid
import datetime
from sqlalchemy.orm import Session
from typing import Dict, Any, List, Tuple, Optional

from app.config.config import settings
from app.database import models
from app.security import encryption

class ZohoOAuthService:
    """
    Handles secure OAuth 2.0 connection, state validations, code exchanges,
    and automatic token refreshes.
    """
    
    @staticmethod
    def generate_state(db: Session) -> str:
        """
        Generates a secure random state string, logs it in PendingState, and returns it.
        """
        state = uuid.uuid4().hex
        pending = models.PendingState(state=state)
        db.add(pending)
        db.commit()
        return state

    @staticmethod
    def validate_state(db: Session, state: str) -> bool:
        """
        Validates state from callback. Must exist and be under 5 minutes old.
        One-time use (deletes after validation).
        """
        if not state:
            return False
            
        pending = db.query(models.PendingState).filter(models.PendingState.state == state).first()
        if not pending:
            return False
            
        # Check expiry (5 minutes)
        now = datetime.datetime.utcnow()
        elapsed = now - pending.created_at
        is_valid = elapsed.total_seconds() <= 300
        
        # Delete state (prevent replay attacks)
        db.delete(pending)
        db.commit()
        return is_valid

    @staticmethod
    def exchange_code(db: Session, code: str, accounts_server: Optional[str] = None) -> models.ZohoCredential:
        """
        Exchanges code for access/refresh tokens. Retrieves organization details
        and saves credentials.
        """
        # Determine accounts server URL
        accounts_base = accounts_server if accounts_server else settings.ZOHO_ACCOUNTS_URL
        token_url = f"{accounts_base.rstrip('/')}/oauth/v2/token"
        
        payload = {
            "code": code,
            "client_id": settings.ZOHO_CLIENT_ID,
            "client_secret": settings.ZOHO_CLIENT_SECRET,
            "redirect_uri": settings.ZOHO_REDIRECT_URI,
            "grant_type": "authorization_code"
        }
        
        # Exchange token
        response = httpx.post(token_url, data=payload, timeout=15.0)
        if response.status_code != 200:
            raise ValueError(f"OAuth code exchange failed: {response.text}")
            
        res_data = response.json()
        if "error" in res_data:
            raise ValueError(f"OAuth error: {res_data.get('error_description', res_data['error'])}")
            
        access_token = res_data["access_token"]
        refresh_token = res_data.get("refresh_token") # Only returned during initial consent
        expires_in = res_data["expires_in"]
        api_domain = res_data.get("api_domain", settings.ZOHO_API_URL)
        scopes_resp = res_data.get("scope", "ZohoExpense.expensereport.READ ZohoExpense.orgsettings.READ ZohoExpense.expense.CREATE")
        
        # Compute absolute expiry timestamp in UTC
        expires_at = datetime.datetime.utcnow() + datetime.timedelta(seconds=expires_in)
        
        # Get existing credentials
        cred = db.query(models.ZohoCredential).first()
        
        # Keep old refresh token if new one is not returned during reauthorization
        stored_refresh = refresh_token
        if not stored_refresh and cred:
            stored_refresh = encryption.decrypt_token(cred.encrypted_refresh_token)
            
        if not stored_refresh:
            raise ValueError("No refresh token received from Zoho. Please revoke access and connect again.")

        # Temporarily create/update credentials so we can make the organizations request
        enc_access = encryption.encrypt_token(access_token)
        enc_refresh = encryption.encrypt_token(stored_refresh)
        
        now_utc = datetime.datetime.utcnow()
        if not cred:
            cred = models.ZohoCredential(
                api_domain=api_domain,
                encrypted_access_token=enc_access,
                encrypted_refresh_token=enc_refresh,
                expires_at=expires_at,
                scopes=scopes_resp,
                connected_at=now_utc
            )
            db.add(cred)
        else:
            cred.api_domain = api_domain
            cred.encrypted_access_token = enc_access
            cred.encrypted_refresh_token = enc_refresh
            cred.expires_at = expires_at
            cred.scopes = scopes_resp
            cred.connected_at = now_utc
        db.commit()
        db.refresh(cred)

        # Retrieve organization details automatically to save organization_id and organization_name
        try:
            orgs = ZohoExpenseClient.get_organizations_direct(api_domain, access_token)
            if orgs:
                # Default to first organization
                primary_org = orgs[0]
                cred.organization_id = str(primary_org.get("organization_id"))
                cred.organization_name = primary_org.get("name")
                db.commit()
        except Exception as e:
            # Don't fail the exchange, but log it
            pass
            
        return cred

    @staticmethod
    def refresh_access_token(db: Session) -> str:
        """
        Evaluates active credentials. If expired or expiring within 5 minutes, 
        performs a refresh with Zoho accounts, updates local record, and returns token.
        """
        cred = db.query(models.ZohoCredential).first()
        if not cred:
            raise ValueError("No credentials found. Zoho Expense is not connected.")
            
        now = datetime.datetime.utcnow()
        # If token is valid for another 5 minutes, return it
        if cred.expires_at > (now + datetime.timedelta(minutes=5)):
            return encryption.decrypt_token(cred.encrypted_access_token)
            
        # Refresh required
        refresh_token = encryption.decrypt_token(cred.encrypted_refresh_token)
        accounts_base = settings.ZOHO_ACCOUNTS_URL
        token_url = f"{accounts_base.rstrip('/')}/oauth/v2/token"
        
        payload = {
            "refresh_token": refresh_token,
            "client_id": settings.ZOHO_CLIENT_ID,
            "client_secret": settings.ZOHO_CLIENT_SECRET,
            "grant_type": "refresh_token"
        }
        
        response = httpx.post(token_url, data=payload, timeout=15.0)
        if response.status_code != 200:
            # Handle possible revocation/invalid grant errors
            if response.status_code == 400:
                raise ValueError("Zoho connection is invalid or has been revoked. Please reconnect.")
            raise ValueError(f"Failed to refresh Zoho token: {response.text}")
            
        res_data = response.json()
        if "error" in res_data:
            raise ValueError(f"Zoho token refresh error: {res_data.get('error')}")
            
        access_token = res_data["access_token"]
        expires_in = res_data["expires_in"]
        
        # Save refreshed values
        cred.encrypted_access_token = encryption.encrypt_token(access_token)
        cred.expires_at = now + datetime.timedelta(seconds=expires_in)
        db.commit()
        
        return access_token

    @staticmethod
    def revoke_token(db: Session):
        """
        Revokes token from Zoho Accounts and removes the local database record.
        """
        cred = db.query(models.ZohoCredential).first()
        if not cred:
            return
            
        refresh_token = encryption.decrypt_token(cred.encrypted_refresh_token)
        accounts_base = settings.ZOHO_ACCOUNTS_URL
        revoke_url = f"{accounts_base.rstrip('/')}/oauth/v2/token/revoke"
        
        try:
            # Revoke refresh token
            httpx.post(revoke_url, params={"token": refresh_token}, timeout=15.0)
        except Exception:
            # Proceed with local cleanup even if Zoho connection fails
            pass
            
        db.delete(cred)
        db.commit()


class ZohoExpenseClient:
    """
    Handles calling read-only Zoho Expense API endpoints, incorporating headers.
    """
    
    @staticmethod
    def get_auth_headers(db: Session) -> Tuple[Dict[str, str], str]:
        """
        Retrieves authorization headers and base api endpoint.
        Returns:
            (headers_dict, api_domain)
        """
        cred = db.query(models.ZohoCredential).first()
        if not cred:
            raise ValueError("Zoho Expense is not connected.")
            
        # Refresh token if necessary
        access_token = ZohoOAuthService.refresh_access_token(db)
        
        # Build headers
        headers = {
            "Authorization": f"Zoho-oauthtoken {access_token}"
        }
        if cred.organization_id:
            headers["X-com-zoho-expense-organizationid"] = cred.organization_id
            
        return headers, cred.api_domain

    @staticmethod
    def get_organizations_direct(api_domain: str, access_token: str) -> List[Dict[str, Any]]:
        """Used during OAuth exchange before organization metadata is saved."""
        url = f"{api_domain.rstrip('/')}/expense/v1/organizations"
        headers = {
            "Authorization": f"Zoho-oauthtoken {access_token}"
        }
        response = httpx.get(url, headers=headers, timeout=15.0)
        if response.status_code != 200:
            raise ValueError(f"Failed to fetch organization settings: {response.text}")
        return response.json().get("organizations", [])

    @classmethod
    def test_connection(cls, db: Session) -> bool:
        """
        Checks connection status by making a safe read request to organizations.
        """
        try:
            headers, api_domain = cls.get_auth_headers(db)
            url = f"{api_domain.rstrip('/')}/expense/v1/organizations"
            response = httpx.get(url, headers=headers, timeout=15.0)
            return response.status_code == 200
        except Exception:
            return False

    @classmethod
    def get_reports(cls, db: Session) -> List[Dict[str, Any]]:
        """
        Retrieves expense reports from Zoho.
        Filters for usable status options ('draft', 'submitted', 'approved').
        """
        import logging
        logger = logging.getLogger("app.services.zoho.client")
        
        headers, api_domain = cls.get_auth_headers(db)
        url = f"{api_domain.rstrip('/')}/expense/v1/expensereports"
        
        params = {
            "page": 1,
            "per_page": 200
        }
        
        org_presence = "present" if headers.get("X-com-zoho-expense-organizationid") else "absent"
        logger.info(
            f"Zoho report request:\n"
            f"GET {url}\n"
            f"organization_id: {org_presence}\n"
            f"page: 1\n"
            f"per_page: 200"
        )
        
        # Pull reports list
        response = httpx.get(url, headers=headers, params=params, timeout=15.0)
        
        if response.status_code == 429:
            # Zoho Rate limit handler
            raise ValueError("Zoho API rate limit reached. Please wait and try again.")
        elif response.status_code != 200:
            raise ValueError(f"Failed to fetch reports from Zoho: {response.text}")
            
        data = response.json()
        reports = data.get("expense_reports") or data.get("expensereports") or []
        
        logger.info(
            f"Response:\n"
            f"HTTP {response.status_code}\n"
            f"top-level keys: {list(data.keys())}\n"
            f"report count: {len(reports)}"
        )
        
        # Safe log status and details of each report
        for idx, r in enumerate(reports):
            logger.info(
                f"Report {idx + 1}:\n"
                f"name = {r.get('report_name') or r.get('name')}\n"
                f"report_id presence = {'present' if r.get('report_id') else 'absent'}\n"
                f"status = {r.get('status')}\n"
                f"start_date = {r.get('start_date') or 'N/A'}\n"
                f"end_date = {r.get('end_date') or 'N/A'}"
            )
            
        # Only return reports in suitable statuses
        # Draft reports are the primary target for adding new expenses
        allowed_statuses = ["draft", "submitted", "approved"]
        filtered_reports = []
        for r in reports:
            status_val = str(r.get("status", "")).lower().strip()
            if status_val in allowed_statuses:
                filtered_reports.append(r)
                
        return filtered_reports

    @classmethod
    def get_report_details(cls, db: Session, report_id: str) -> Dict[str, Any]:
        """
        Fetches detailed record parameters for a specific expense report.
        """
        headers, api_domain = cls.get_auth_headers(db)
        url = f"{api_domain.rstrip('/')}/expense/v1/expensereports/{report_id}"
        
        response = httpx.get(url, headers=headers, timeout=15.0)
        if response.status_code == 404:
            raise ValueError(f"Report ID '{report_id}' was not found in Zoho.")
        elif response.status_code != 200:
            raise ValueError(f"Failed to fetch report details: {response.text}")
            
        data = response.json()
        return data.get("expense_report") or data.get("expensereport") or {}

    @classmethod
    def create_expense(cls, db: Session, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Sends request to create exactly ONE expense in Zoho.
        Does not submit any report. Includes exponential backoff for 429 rate limits.
        """
        import time
        import logging
        logger = logging.getLogger("app.services.zoho.client")

        backoff = 2.0  # seconds
        max_retries = 3
        
        for attempt in range(max_retries):
            headers, api_domain = cls.get_auth_headers(db)
            url = f"{api_domain.rstrip('/')}/expense/v1/expenses"
            
            try:
                response = httpx.post(url, headers=headers, json=payload, timeout=25.0)
                
                # Check for rate limiting
                if response.status_code == 429:
                    retry_after = response.headers.get("Retry-After")
                    wait_time = float(retry_after) if retry_after else backoff
                    logger.warning(f"Zoho API Rate Limit (429) hit. Waiting {wait_time}s before retry (attempt {attempt + 1})...")
                    time.sleep(wait_time)
                    backoff *= 2.0
                    continue
                    
                if response.status_code != 201 and response.status_code != 200:
                    # Try parsing error details safely
                    try:
                        err_data = response.json()
                        err_msg = err_data.get("message", response.text)
                    except Exception:
                        err_msg = response.text
                    raise ValueError(f"Zoho rejected expense creation: {err_msg}")
                    
                res_data = response.json()
                if "expense" in res_data:
                    return res_data["expense"]
                elif "expenses" in res_data and isinstance(res_data["expenses"], list) and len(res_data["expenses"]) > 0:
                    return res_data["expenses"][0]
                return res_data
                
            except httpx.HTTPError as e:
                if attempt == max_retries - 1:
                    raise ValueError(f"Zoho API network error: {str(e)}")
                logger.warning(f"Zoho API network error. Waiting {backoff}s before retry (attempt {attempt + 1})...")
                time.sleep(backoff)
                backoff *= 2.0

        raise ValueError("Zoho rejected expense creation: Repeatedly hit rate limits (429).")


def normalize_string(s: str) -> str:
    import unicodedata
    import re
    if not s:
        return ""
    # Unicode normalize NFC
    s_norm = unicodedata.normalize("NFC", str(s))
    # Whitespace normalize (replace multiple spaces/tabs with single space)
    s_norm = re.sub(r"\s+", " ", s_norm)
    # Trim and lower
    return s_norm.strip().lower()


class ZohoEntityResolver:
    """
    Resolves Excel text fields into Zoho internal IDs by querying respective Zoho APIs
    and performing exact normalized case-insensitive matching.
    Uses ZohoMasterDataService for paginated, cached lookups.
    """
    
    @classmethod
    def clear_cache(cls):
        """Clears master data cache."""
        from app.services.zoho.master_data import ZohoMasterDataService
        ZohoMasterDataService.clear_cache()

    @staticmethod
    def _find_match(items: List[Dict[str, Any]], search_value: str, name_key: str = "name") -> Optional[Dict[str, Any]]:
        target = normalize_string(search_value)
        if not target:
            return None
            
        matched = []
        for item in items:
            item_name = item.get(name_key, "")
            if normalize_string(item_name) == target:
                matched.append(item)
                
        if not matched:
            return None
        return matched[0]

    @classmethod
    def resolve_category(cls, db: Session, category_name: str) -> str:
        if not category_name or not str(category_name).strip():
            raise ValueError("Category name is blank.")
            
        from app.services.zoho.master_data import ZohoMasterDataService
        categories = ZohoMasterDataService.get_categories(db)
        match = cls._find_match(categories, category_name)
        if match:
            return str(match["id"])
            
        raise ValueError(f"Cannot create this expense because category '{category_name}' could not be found in Zoho Expense.")

    @classmethod
    def resolve_project(cls, db: Session, project_name: str) -> Optional[str]:
        if not project_name or not str(project_name).strip():
            return None
            
        from app.services.zoho.master_data import ZohoMasterDataService
        projects = ZohoMasterDataService.get_projects(db)
        match = cls._find_match(projects, project_name)
        if match:
            return str(match["id"])
            
        raise ValueError(f"Project '{project_name}' could not be found in Zoho Expense.")

    @classmethod
    def resolve_vendor(cls, db: Session, vendor_name: str) -> str:
        if not vendor_name or not str(vendor_name).strip():
            raise ValueError("Vendor Name is blank.")
        return str(vendor_name).strip()

    @classmethod
    def resolve_tax(cls, db: Session, tax_name: str) -> Optional[str]:
        if not tax_name or not str(tax_name).strip():
            return None
        if tax_name == "none" or normalize_string(tax_name) == "none":
            return "none"
            
        from app.services.zoho.master_data import ZohoMasterDataService
        taxes = ZohoMasterDataService.get_taxes(db)
        match = cls._find_match(taxes, tax_name)
        if match:
            return str(match["id"])
            
        raise ValueError(f"Tax Type '{tax_name}' could not be found in Zoho Expense.")

    @classmethod
    def resolve_paid_through(cls, db: Session, paid_through: str) -> str:
        if not paid_through or not str(paid_through).strip():
            raise ValueError("Paid Through account is blank.")
            
        from app.services.zoho.master_data import ZohoMasterDataService
        modes = ZohoMasterDataService.get_payment_modes(db)
        
        target = normalize_string(paid_through)
        
        import re
        def clean_name(n: str) -> str:
            cleaned = re.sub(r'^\d+\.\s*', '', n)
            return normalize_string(cleaned)
            
        for mode in modes:
            if normalize_string(mode["name"]) == target or clean_name(mode["name"]) == target:
                return str(mode["id"])
                
        raise ValueError(f"Cannot create this expense because Paid Through '{paid_through}' could not be found in Zoho Expense.")

    @classmethod
    def resolve_expense_kind(cls, db: Session, expense_kind: str) -> str:
        if not expense_kind or not str(expense_kind).strip():
            raise ValueError("Expense Kind is blank.")
            
        from app.services.zoho.master_data import ZohoMasterDataService
        kinds = ZohoMasterDataService.get_expense_kinds(db)
        match = cls._find_match(kinds, expense_kind)
        if match:
            return str(match["id"])
            
        raise ValueError(f"Cannot create this expense because Expense Kind '{expense_kind}' could not be found in Zoho Expense.")

    @classmethod
    def resolve_gst_non_gst(cls, db: Session, gst_val: str) -> str:
        if not gst_val or not str(gst_val).strip():
            raise ValueError("GST/Non-GST value is blank.")
            
        # Standardise the excel values for mapping
        target = normalize_string(gst_val)
        if target in ["gst", "gst type"]:
            gst_norm = "GST"
        elif target in ["non-gst", "non gst", "non_gst"]:
            gst_norm = "Non-GST"
        else:
            raise ValueError(f"Cannot create this expense because GST/Non-GST '{gst_val}' could not be found in Zoho Expense.")
            
        from app.services.zoho.master_data import ZohoMasterDataService
        gst_options = ZohoMasterDataService.get_gst_options(db)
        match = cls._find_match(gst_options, gst_norm)
        if match:
            return str(match["id"])
            
        raise ValueError(f"Cannot create this expense because GST/Non-GST '{gst_val}' could not be found in Zoho Expense.")
