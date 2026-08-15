import urllib.parse
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.database.session import get_db
from app.database import models
from app.services.zoho.client import ZohoOAuthService, ZohoExpenseClient, ZohoEntityResolver
from app.config.config import settings

router = APIRouter()

# Frontend home redirect URL for callbacks
FRONTEND_HOME = "http://localhost:5173"

@router.get("/status")
def get_zoho_status(db: Session = Depends(get_db)):
    """
    Returns the Zoho connection state and organization details.
    """
    cred = db.query(models.ZohoCredential).first()
    if not cred:
        return {"connected": False, "organization": None}
        
    return {
        "connected": True,
        "organization": cred.organization_name
    }

@router.get("/connect")
def initiate_zoho_connection(db: Session = Depends(get_db)):
    """
    Generates a secure state parameter, stores it locally, and redirects 
    the user to the Zoho Expense authorization grant page.
    """
    if not settings.ZOHO_CLIENT_ID or not settings.ZOHO_CLIENT_SECRET:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Zoho client credentials are not configured in settings. Check .env config."
        )

    state = ZohoOAuthService.generate_state(db)
    
    # URL Encode Redirect URI
    redirect_uri_enc = urllib.parse.quote(settings.ZOHO_REDIRECT_URI)
    
    # Request access_type=offline and prompt=consent to ensure we get a refresh token
    scope = "ZohoExpense.expensereport.READ,ZohoExpense.orgsettings.READ,ZohoExpense.expense.CREATE,ZohoExpense.expensecategory.READ,ZohoExpense.project.READ,ZohoExpense.contacts.READ,ZohoExpense.tax.READ,ZohoExpense.settings.READ"
    
    auth_url = (
        f"{settings.ZOHO_ACCOUNTS_URL.rstrip('/')}/oauth/v2/auth?"
        f"scope={scope}&"
        f"client_id={settings.ZOHO_CLIENT_ID}&"
        f"response_type=code&"
        f"redirect_uri={redirect_uri_enc}&"
        f"state={state}&"
        f"access_type=offline&"
        f"prompt=consent"
    )
    
    return RedirectResponse(auth_url)

@router.get("/callback")
def oauth_callback(
    code: str = Query(None),
    state: str = Query(None),
    error: str = Query(None),
    accounts_server: str = Query(None, alias="accounts-server"),
    db: Session = Depends(get_db)
):
    """
    Handles user redirection from Zoho Expense OAuth page.
    Validates anti-forgery states, exchanges codes, and completes connection.
    """
    if error:
        err_msg = urllib.parse.quote(f"Authentication failed: {error}")
        return RedirectResponse(f"{FRONTEND_HOME}/?connection=error&error={err_msg}")
        
    if not code or not state:
        err_msg = urllib.parse.quote("Missing code or state parameters from authorization callback.")
        return RedirectResponse(f"{FRONTEND_HOME}/?connection=error&error={err_msg}")

    # Validate state CSRF token
    if not ZohoOAuthService.validate_state(db, state):
        err_msg = urllib.parse.quote("Invalid or expired OAuth security state. Cross-site request rejected.")
        return RedirectResponse(f"{FRONTEND_HOME}/?connection=error&error={err_msg}")

    try:
        # Complete authorization code exchange
        ZohoOAuthService.exchange_code(db, code, accounts_server)
        return RedirectResponse(f"{FRONTEND_HOME}/?connection=success")
    except Exception as e:
        err_msg = urllib.parse.quote(str(e))
        return RedirectResponse(f"{FRONTEND_HOME}/?connection=error&error={err_msg}")

@router.post("/disconnect")
def disconnect_zoho(db: Session = Depends(get_db)):
    """
    Clears local database tokens, revokes authorization access in Zoho Accounts, 
    and disconnects the integration.
    """
    try:
        ZohoOAuthService.revoke_token(db)
        return {"message": "Successfully disconnected from Zoho Expense."}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Disconnect failed: {str(e)}"
        )

@router.get("/test")
def test_zoho_connection(db: Session = Depends(get_db)):
    """
    Runs diagnostic requests to confirm token validations.
    """
    is_ok = ZohoExpenseClient.test_connection(db)
    if is_ok:
        return {"status": "success", "message": "Zoho Expense connection is working."}
        
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Unable to connect to Zoho Expense. Token might have expired or credentials changed."
    )

@router.get("/reports")
def get_reports_list(db: Session = Depends(get_db)):
    """
    Fetches the list of active/draft expense reports.
    """
    try:
        reports = ZohoExpenseClient.get_reports(db)
        return reports
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unable to retrieve expense reports: {str(e)}"
        )

@router.get("/reports/{report_id}")
def get_report_details(report_id: str, db: Session = Depends(get_db)):
    """
    Fetches metadata details for a specific report.
    """
    try:
        details = ZohoExpenseClient.get_report_details(db, report_id)
        return details
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unable to retrieve report details: {str(e)}"
        )

class TestExpenseCreateRequest(BaseModel):
    record_id: int
    gst_report_id: str
    nongst_report_id: str
    category_id: Optional[str] = None
    project_id: Optional[str] = None
    vendor_name: Optional[str] = None
    tax_id: Optional[str] = None
    paid_through_id: Optional[str] = None
    expense_kind_id: Optional[str] = None
    gst_non_gst_id: Optional[str] = None

@router.get("/check-scopes")
def check_zoho_scopes(db: Session = Depends(get_db)):
    """
    Checks if connected credentials have all required scopes for listing and creating.
    """
    cred = db.query(models.ZohoCredential).first()
    if not cred:
        return {"connected": False, "has_create_scope": False}
        
    scopes_str = cred.scopes or ""
    scopes_list = [s.strip() for s in scopes_str.replace(",", " ").split(" ") if s.strip()]
    
    required_scopes = [
        "ZohoExpense.expense.CREATE",
        "ZohoExpense.expensereport.READ",
        "ZohoExpense.orgsettings.READ",
        "ZohoExpense.expensecategory.READ",
        "ZohoExpense.project.READ",
        "ZohoExpense.contacts.READ",
        "ZohoExpense.tax.READ",
        "ZohoExpense.settings.READ"
    ]
    
    has_all = all(req_scope in scopes_list for req_scope in required_scopes)
    
    return {
        "connected": True,
        "has_create_scope": has_all
    }

@router.post("/expenses/test-create")
def create_test_expense(req: TestExpenseCreateRequest, db: Session = Depends(get_db)):
    """
    Resolves entity IDs for exactly ONE Excel record and creates it in Zoho.
    """
    # 1. Fetch record from DB
    record = db.query(models.ExpenseRecord).filter(models.ExpenseRecord.id == req.record_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Expense record not found in local database.")
        
    if record.status != "VALID":
        raise HTTPException(status_code=400, detail="Cannot create expense for an invalid spreadsheet row.")
        
    # 2. Determine target report
    report_id = req.gst_report_id if record.gst_type == "GST" else req.nongst_report_id
    if not report_id:
        raise HTTPException(status_code=400, detail="No target report specified for this expense routing category.")
        
    # Get report name (for logging)
    report_name = "Unknown Report"
    try:
        report_info = ZohoExpenseClient.get_report_details(db, report_id)
        report_name = report_info.get("report_name", "Unknown Report")
    except Exception:
        pass
        
    # 3. Resolve IDs
    error_field = None
    try:
        error_field = "Category"
        category_id = req.category_id or ZohoEntityResolver.resolve_category(db, record.category)
        
        error_field = "Project"
        project_id = req.project_id
        if not project_id and record.project:
            project_id = ZohoEntityResolver.resolve_project(db, record.project)
            
        error_field = "Vendor Name"
        merchant_name = req.vendor_name or record.vendor_name
        if merchant_name:
            merchant_name = str(merchant_name).strip()
            
        error_field = "Tax Type"
        tax_id = req.tax_id
        if not tax_id and record.tax_type:
            tax_id = ZohoEntityResolver.resolve_tax(db, record.tax_type)
            
        if tax_id == "none":
            tax_id = None
            
        error_field = "Paid Through"
        paid_through_id = req.paid_through_id or (ZohoEntityResolver.resolve_paid_through(db, record.paid_through) if record.paid_through else None)
        if not paid_through_id and record.paid_through:
            raise ValueError(f"Cannot create this expense because Paid Through '{record.paid_through}' could not be found in Zoho Expense.")
            
        # Determine payment mode string based on resolved account ID
        payment_mode = "cash"
        if paid_through_id == "668650000000904009":
            payment_mode = "Bank Transfer"
        elif paid_through_id == "668650000000000573":
            payment_mode = "Cash"
            
        error_field = "Expense Kind"
        expense_kind_id = req.expense_kind_id or (ZohoEntityResolver.resolve_expense_kind(db, record.expense_kind) if record.expense_kind else None)
        if not expense_kind_id and record.expense_kind:
            raise ValueError(f"Cannot create this expense because Expense Kind '{record.expense_kind}' could not be found in Zoho Expense.")
            
        error_field = "GST/Non-GST"
        gst_non_gst_id = req.gst_non_gst_id or (ZohoEntityResolver.resolve_gst_non_gst(db, record.gst_type) if record.gst_type else None)
        if not gst_non_gst_id and record.gst_type:
            raise ValueError(f"Cannot create this expense because GST/Non-GST '{record.gst_type}' could not be found in Zoho Expense.")
        
    except Exception as e:
        # Log failure in database
        audit = models.ZohoAuditLog(
            excel_row=record.original_row_number,
            amount=record.amount or 0.0,
            description=record.description or "",
            destination_report=report_name,
            result="FAILED",
            error_details=f"Field: {error_field}. Error: {str(e)}"
        )
        db.add(audit)
        db.commit()
        
        return {
            "status": "error",
            "field": error_field,
            "message": str(e)
        }
        
    # Get base currency ID dynamically
    currency_id = ZohoMasterDataService.get_base_currency(db)
        
    # 4. Construct payload
    payload = {
        "date": record.expense_date,
        "amount": record.amount,
        "category_id": category_id,
        "description": record.description,
        "report_id": report_id,
        "paid_through_account_id": paid_through_id,
        "payment_mode": payment_mode,
        "currency_id": currency_id
    }
    if merchant_name:
        payload["merchant"] = merchant_name
    if project_id:
        payload["project_id"] = project_id
    if tax_id:
        payload["tax_id"] = tax_id
        
    # Construct custom fields payload
    custom_fields = []
    if merchant_name:
        custom_fields.append({
            "customfield_id": "668650000004152025",
            "value": merchant_name
        })
    if expense_kind_id:
        kind_name = "Project Expense_v1" if expense_kind_id == "668650000004152045" else "Corporate Overhead Expense_v1"
        custom_fields.append({
            "customfield_id": "668650000004152041",
            "value": kind_name
        })
    if gst_non_gst_id:
        gst_opt_name = "GST" if gst_non_gst_id == "668650000004152055" else "Non-GST"
        custom_fields.append({
            "customfield_id": "668650000004152053",
            "value": gst_opt_name
        })
        
    if custom_fields:
        payload["custom_fields"] = custom_fields
        
    # 5. Call Zoho Expense POST /expenses
    try:
        created_expense = ZohoExpenseClient.create_expense(db, payload)
        zoho_expense_id = created_expense.get("expense_id") or created_expense.get("id")
        
        # Log success
        audit = models.ZohoAuditLog(
            excel_row=record.original_row_number,
            amount=record.amount or 0.0,
            description=record.description or "",
            destination_report=report_name,
            result="SUCCESS",
            zoho_expense_id=zoho_expense_id
        )
        db.add(audit)
        db.commit()
        
        return {
            "status": "success",
            "expense_id": zoho_expense_id,
            "amount": record.amount,
            "description": record.description,
            "excel_row": record.original_row_number,
            "report_name": report_name
        }
    except Exception as e:
        # Log failure in database
        audit = models.ZohoAuditLog(
            excel_row=record.original_row_number,
            amount=record.amount or 0.0,
            description=record.description or "",
            destination_report=report_name,
            result="FAILED",
            error_details=f"API Post Error: {str(e)}"
        )
        db.add(audit)
        db.commit()
        
        return {
            "status": "error",
            "field": "Zoho API",
            "message": str(e)
        }

from app.services.zoho.master_data import ZohoMasterDataService

@router.get("/master-data/categories")
def get_master_categories(db: Session = Depends(get_db)):
    try:
        return ZohoMasterDataService.get_categories(db)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch categories: {str(e)}")

@router.get("/master-data/projects")
def get_master_projects(db: Session = Depends(get_db)):
    try:
        return ZohoMasterDataService.get_projects(db)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch projects: {str(e)}")

@router.get("/master-data/vendors")
def get_master_vendors(db: Session = Depends(get_db)):
    try:
        return ZohoMasterDataService.get_vendors(db)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch vendors: {str(e)}")

@router.get("/master-data/taxes")
def get_master_taxes(db: Session = Depends(get_db)):
    try:
        return ZohoMasterDataService.get_taxes(db)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch taxes: {str(e)}")

@router.get("/master-data/payment-modes")
def get_master_payment_modes(db: Session = Depends(get_db)):
    try:
        return ZohoMasterDataService.get_payment_modes(db)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch payment modes: {str(e)}")

@router.get("/master-data/expense-kinds")
def get_master_expense_kinds(db: Session = Depends(get_db)):
    try:
        return ZohoMasterDataService.get_expense_kinds(db)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch expense kinds: {str(e)}")

@router.get("/master-data/gst-options")
def get_master_gst_options(db: Session = Depends(get_db)):
    try:
        return ZohoMasterDataService.get_gst_options(db)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch GST options: {str(e)}")

@router.post("/master-data/refresh-cache")
def refresh_master_cache():
    ZohoMasterDataService.clear_cache()
    return {"status": "success", "message": "Master data cache cleared."}


from typing import Dict
from fastapi import BackgroundTasks
from fastapi.responses import StreamingResponse
import io
import openpyxl
from app.services.zoho.bulk_processor import run_bulk_create_task

class DryRunRequest(BaseModel):
    session_id: int
    gst_report_id: str
    nongst_report_id: str

@router.post("/expenses/dry-run")
def dry_run_preview(req: DryRunRequest, db: Session = Depends(get_db)):
    session = db.query(models.UploadSession).filter(models.UploadSession.id == req.session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Upload session not found.")
        
    # Validate reports exist and are active
    try:
        gst_report = ZohoExpenseClient.get_report_details(db, req.gst_report_id)
        if not gst_report:
            raise ValueError("GST Report not found or inaccessible in Zoho.")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"GST Report Validation Error: {str(e)}")
        
    try:
        nongst_report = ZohoExpenseClient.get_report_details(db, req.nongst_report_id)
        if not nongst_report:
            raise ValueError("NON-GST Report not found or inaccessible in Zoho.")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"NON-GST Report Validation Error: {str(e)}")
        
    # Count pending valid rows that would be created
    pending_count = db.query(models.ExpenseRecord).filter(
        models.ExpenseRecord.session_id == req.session_id,
        models.ExpenseRecord.status == "VALID",
        models.ExpenseRecord.zoho_status.in_(["PENDING", "FAILED"])
    ).count()
    
    return {
        "status": "success",
        "excel_rows": session.total_rows,
        "valid_rows": session.valid_rows,
        "invalid_rows": session.invalid_rows,
        "gst_rows": session.gst_count,
        "nongst_rows": session.nongst_count,
        "gst_report_name": gst_report.get("report_name") or gst_report.get("name") or "GST Report",
        "nongst_report_name": nongst_report.get("report_name") or nongst_report.get("name") or "NON-GST Report",
        "would_create": pending_count,
        "changes_made": 0
    }

class BulkCreateRequest(BaseModel):
    session_id: int
    gst_report_id: str
    nongst_report_id: str
    skip_invalid: bool = False
    limit: Optional[int] = None
    category_mappings: Optional[Dict[str, str]] = None
    project_mappings: Optional[Dict[str, str]] = None
    tax_mappings: Optional[Dict[str, str]] = None
    paid_through_mappings: Optional[Dict[str, str]] = None
    expense_kind_mappings: Optional[Dict[str, str]] = None
    gst_non_gst_mappings: Optional[Dict[str, str]] = None

@router.post("/expenses/bulk-create")
def bulk_create_expenses(req: BulkCreateRequest, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    session = db.query(models.UploadSession).filter(models.UploadSession.id == req.session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Upload session not found.")
        
    if session.status == "CREATING":
        raise HTTPException(status_code=400, detail="A bulk upload task is already running for this session.")
        
    # Reset all failed or cancelled rows to PENDING before starting/retrying
    db.query(models.ExpenseRecord).filter(
        models.ExpenseRecord.session_id == req.session_id,
        models.ExpenseRecord.zoho_status.in_(["FAILED", "CANCELLED"])
    ).update({"zoho_status": "PENDING", "zoho_error": None}, synchronize_session=False)
    
    # Save resolved mappings snapshot for audit/production reproducibility
    import json
    snapshot = {
        "category_mappings": req.category_mappings or {},
        "project_mappings": req.project_mappings or {},
        "tax_mappings": req.tax_mappings or {},
        "paid_through_mappings": req.paid_through_mappings or {},
        "expense_kind_mappings": req.expense_kind_mappings or {},
        "gst_non_gst_mappings": req.gst_non_gst_mappings or {}
    }
    session.mapping_snapshot = json.dumps(snapshot)
    session.selected_gst_report_id = req.gst_report_id
    session.selected_nongst_report_id = req.nongst_report_id
    
    # Set session status to CREATING synchronously to prevent race conditions during initial polling
    session.status = "CREATING"
    db.commit()

    background_tasks.add_task(
        run_bulk_create_task,
        session_id=req.session_id,
        gst_report_id=req.gst_report_id,
        nongst_report_id=req.nongst_report_id,
        skip_invalid=req.skip_invalid,
        limit=req.limit,
        category_mappings=req.category_mappings,
        project_mappings=req.project_mappings,
        tax_mappings=req.tax_mappings,
        paid_through_mappings=req.paid_through_mappings,
        expense_kind_mappings=req.expense_kind_mappings,
        gst_non_gst_mappings=req.gst_non_gst_mappings
    )
    
    return {"status": "success", "message": "Bulk creation task started."}

@router.get("/expenses/bulk-status")
def get_bulk_status(session_id: int, db: Session = Depends(get_db)):
    session = db.query(models.UploadSession).filter(models.UploadSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Upload session not found.")
        
    records = db.query(models.ExpenseRecord).filter(
        models.ExpenseRecord.session_id == session_id
    ).order_by(models.ExpenseRecord.original_row_number).all()
    
    total = len(records)
    created = sum(1 for r in records if r.zoho_status == "CREATED")
    failed = sum(1 for r in records if r.zoho_status == "FAILED")
    creating = sum(1 for r in records if r.zoho_status == "CREATING")
    skipped = sum(1 for r in records if r.zoho_status == "SKIPPED")
    pending = sum(1 for r in records if r.zoho_status == "PENDING")
    
    current_row = None
    current_status = "IDLE"
    
    active_row = next((r for r in records if r.zoho_status == "CREATING"), None)
    if active_row:
        current_row = active_row.original_row_number
        current_status = "CREATING"
    else:
        last_row = next((r for r in reversed(records) if r.zoho_status in ["CREATED", "FAILED"]), None)
        if last_row:
            current_row = last_row.original_row_number
            current_status = last_row.zoho_status
            
    results = [
        {
            "id": r.id,
            "original_row_number": r.original_row_number,
            "expense_date": r.expense_date,
            "amount": r.amount,
            "description": r.description,
            "gst_type": r.gst_type,
            "category": r.category,
            "paid_through": r.paid_through,
            "vendor_name": r.vendor_name,
            "zoho_status": r.zoho_status or "PENDING",
            "zoho_expense_id": r.zoho_expense_id,
            "zoho_error": r.zoho_error,
            "destination_report_id": r.destination_report_id,
            "error_code": r.error_code,
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "updated_at": r.updated_at.isoformat() if r.updated_at else None
        }
        for r in records
    ]
    
    return {
        "status": session.status,
        "is_running": session.status == "CREATING",
        "upload_session_id": session.upload_session_id,
        "total_rows": total,
        "processed_count": created + failed + skipped,
        "created_count": created,
        "failed_count": failed,
        "current_row": current_row,
        "current_status": current_status,
        "records": results
    }

@router.get("/sessions/{session_id}/error-report")
def download_error_report(session_id: int, db: Session = Depends(get_db)):
    session = db.query(models.UploadSession).filter(models.UploadSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Upload session not found.")
        
    failed_records = db.query(models.ExpenseRecord).filter(
        models.ExpenseRecord.session_id == session_id,
        models.ExpenseRecord.zoho_status == "FAILED"
    ).order_by(models.ExpenseRecord.original_row_number).all()
    
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Failed Expenses"
    
    headers = [
        "Excel Row", "Expense Date", "Amount", "Description", "Category",
        "Paid Through", "Vendor Name", "Failure Status", "Failure Reason",
        "Error Code", "Destination Report"
    ]
    ws.append(headers)
    
    from openpyxl.styles import Font, Alignment, PatternFill
    header_font = Font(name="Arial", size=10, bold=True, color="FFFFFF")
    header_fill = PatternFill(start_color="1F2937", end_color="1F2937", fill_type="solid")
    header_align = Alignment(horizontal="center", vertical="center")
    
    for col_idx in range(1, len(headers) + 1):
        cell = ws.cell(row=1, column=col_idx)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = header_align
        
    audit_logs = db.query(models.ZohoAuditLog).filter(
        models.ZohoAuditLog.session_id == session_id,
        models.ZohoAuditLog.result == "FAILED"
    ).all()
    audit_reports = {log.excel_row: log.destination_report for log in audit_logs}
    
    for r in failed_records:
        dest_report = audit_reports.get(r.original_row_number, f"Report {r.destination_report_id or ''}")
        row_data = [
            r.original_row_number,
            r.expense_date,
            r.amount,
            r.description,
            r.category,
            r.paid_through,
            r.vendor_name,
            r.zoho_status,
            r.zoho_error,
            r.error_code,
            dest_report
        ]
        ws.append(row_data)
        
    for col in ws.columns:
        vals = [cell.value for cell in col]
        max_len = max(len(str(val or '')) for val in vals) if vals else 10
        col_letter = openpyxl.utils.get_column_letter(col[0].column)
        ws.column_dimensions[col_letter].width = max(max_len + 3, 10)
        
    stream = io.BytesIO()
    wb.save(stream)
    stream.seek(0)
    
    import datetime
    filename = f"error_report_session_{session_id}_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    
    return StreamingResponse(
        stream,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )
