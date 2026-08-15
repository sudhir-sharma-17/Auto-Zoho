import logging
import datetime
from sqlalchemy.orm import Session
from typing import Dict, Any, Optional

from app.database import models
from app.services.zoho.client import ZohoExpenseClient, ZohoEntityResolver
from app.services.zoho.master_data import ZohoMasterDataService

logger = logging.getLogger("app.services.zoho.bulk_processor")

def run_bulk_create_task(
    session_id: int,
    gst_report_id: str,
    nongst_report_id: str,
    skip_invalid: bool = False,
    limit: Optional[int] = None,
    category_mappings: Optional[Dict[str, str]] = None,
    project_mappings: Optional[Dict[str, str]] = None,
    tax_mappings: Optional[Dict[str, str]] = None,
    paid_through_mappings: Optional[Dict[str, str]] = None,
    expense_kind_mappings: Optional[Dict[str, str]] = None,
    gst_non_gst_mappings: Optional[Dict[str, str]] = None,
    db: Optional[Session] = None
):
    """
    Background worker function that processes spreadsheet records in sequence
    and creates real Zoho expenses.
    """
    should_close = False
    if db is None:
        from app.database.session import SessionLocal
        db = SessionLocal()
        should_close = True
    
    try:
        # Get session
        session = db.query(models.UploadSession).filter(models.UploadSession.id == session_id).first()
        if not session:
            logger.error(f"Upload session {session_id} not found.")
            return
            
        session.status = "CREATING"
        db.commit()
        
        # Load all records
        records = db.query(models.ExpenseRecord).filter(
            models.ExpenseRecord.session_id == session_id
        ).order_by(models.ExpenseRecord.original_row_number).all()
        
        # Filter eligible records
        eligible = []
        for r in records:
            # If already created, skip it
            if r.zoho_status == "CREATED":
                continue
                
            # If invalid and we choose to skip invalid rows, skip it
            if r.status == "INVALID":
                if skip_invalid:
                    r.zoho_status = "SKIPPED"
                    r.zoho_error = "Skipped as invalid row during bulk upload selection."
                    continue
                else:
                    # Cancel bulk upload if there's any invalid row and we are not skipping
                    logger.warning("Unresolved invalid rows found, canceling bulk creation.")
                    for p in records:
                        if p.zoho_status in ["PENDING", "CREATING"]:
                            p.zoho_status = "CANCELLED"
                            p.zoho_error = "Cancelled due to presence of invalid rows."
                    session.status = "Failed"
                    db.commit()
                    return
            eligible.append(r)
            
        # Apply limits (e.g. 5-row test / 20-row test)
        if limit is not None:
            eligible = eligible[:limit]
            
        if not eligible:
            logger.info("No eligible records to process.")
            session.status = "Validated"
            db.commit()
            return
            
        # Retrieve report names for logging
        report_names = {}
        for r_id in [gst_report_id, nongst_report_id]:
            if r_id:
                try:
                    info = ZohoExpenseClient.get_report_details(db, r_id)
                    report_names[r_id] = info.get("report_name", f"Report {r_id}")
                except Exception:
                    report_names[r_id] = f"Report {r_id}"
                    
        # Get base currency ID
        currency_id = ZohoMasterDataService.get_base_currency(db)
        
        # Throttling delay between requests (e.g. 0.5s) to respect Zoho rate limits
        import time
        
        for idx, record in enumerate(eligible):
            record.zoho_status = "CREATING"
            db.commit()
            
            # Select target report
            report_id = gst_report_id if record.gst_type == "GST" else nongst_report_id
            record.destination_report_id = report_id
            
            # 1. Resolve category ID
            category_id = None
            if record.category:
                category_id = (category_mappings or {}).get(record.category)
                if not category_id:
                    try:
                        category_id = ZohoEntityResolver.resolve_category(db, record.category)
                    except Exception as e:
                        record.zoho_status = "FAILED"
                        record.zoho_error = f"Category error: {str(e)}"
                        db.commit()
                        continue
                        
            # 2. Resolve project ID
            project_id = None
            if record.project:
                project_id = (project_mappings or {}).get(record.project)
                if not project_id:
                    try:
                        project_id = ZohoEntityResolver.resolve_project(db, record.project)
                    except Exception:
                        pass
                        
            # 3. Resolve tax ID
            tax_id = None
            if record.tax_type:
                tax_id = (tax_mappings or {}).get(record.tax_type)
                if not tax_id:
                    try:
                        tax_id = ZohoEntityResolver.resolve_tax(db, record.tax_type)
                    except Exception:
                        pass
            if tax_id == "none":
                tax_id = None
                
            # 4. Resolve paid through ID
            paid_through_id = None
            if record.paid_through:
                paid_through_id = (paid_through_mappings or {}).get(record.paid_through)
                if not paid_through_id:
                    try:
                        paid_through_id = ZohoEntityResolver.resolve_paid_through(db, record.paid_through)
                    except Exception as e:
                        record.zoho_status = "FAILED"
                        record.zoho_error = f"Paid through error: {str(e)}"
                        db.commit()
                        continue
            if not paid_through_id and record.paid_through:
                record.zoho_status = "FAILED"
                record.zoho_error = f"Cannot create this expense because Paid Through '{record.paid_through}' could not be found in Zoho Expense."
                db.commit()
                continue
                
            # 5. Resolve expense kind ID
            expense_kind_id = None
            if record.expense_kind:
                expense_kind_id = (expense_kind_mappings or {}).get(record.expense_kind)
                if not expense_kind_id:
                    try:
                        expense_kind_id = ZohoEntityResolver.resolve_expense_kind(db, record.expense_kind)
                    except Exception as e:
                        record.zoho_status = "FAILED"
                        record.zoho_error = f"Expense kind error: {str(e)}"
                        db.commit()
                        continue
            if not expense_kind_id and record.expense_kind:
                record.zoho_status = "FAILED"
                record.zoho_error = f"Cannot create this expense because Expense Kind '{record.expense_kind}' could not be found in Zoho Expense."
                db.commit()
                continue
                
            # 6. Resolve GST/Non-GST ID
            gst_non_gst_id = None
            if record.gst_type:
                gst_non_gst_id = (gst_non_gst_mappings or {}).get(record.gst_type)
                if not gst_non_gst_id:
                    try:
                        gst_val = "GST" if record.gst_type == "GST" else "Non-GST"
                        gst_non_gst_id = ZohoEntityResolver.resolve_gst_non_gst(db, gst_val)
                    except Exception as e:
                        record.zoho_status = "FAILED"
                        record.zoho_error = f"GST option error: {str(e)}"
                        db.commit()
                        continue
            if not gst_non_gst_id and record.gst_type:
                record.zoho_status = "FAILED"
                record.zoho_error = f"Cannot create this expense because GST/Non-GST '{record.gst_type}' could not be found in Zoho Expense."
                db.commit()
                continue

            # Determine payment mode string based on resolved account ID
            payment_mode = "cash"
            if paid_through_id == "668650000000904009":
                payment_mode = "Bank Transfer"
            elif paid_through_id == "668650000000000573":
                payment_mode = "Cash"
                
            merchant_name = record.vendor_name
            if merchant_name:
                merchant_name = str(merchant_name).strip()
                
            # Construct Zoho payload
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
                
            # Construct custom fields list
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
                
            # Create Zoho Expense
            try:
                # Zoho API throttler
                time.sleep(0.5)
                
                created_expense = ZohoExpenseClient.create_expense(db, payload)
                zoho_id = created_expense.get("expense_id") or created_expense.get("id")
                
                record.zoho_status = "CREATED"
                record.zoho_expense_id = zoho_id
                record.zoho_error = None
                
                # Write to Audit Log
                audit = models.ZohoAuditLog(
                    session_id=session_id,
                    excel_row=record.original_row_number,
                    amount=record.amount or 0.0,
                    description=record.description or "",
                    destination_report=report_names.get(report_id, f"Report {report_id}"),
                    result="SUCCESS",
                    zoho_expense_id=zoho_id
                )
                db.add(audit)
                db.commit()
                
            except Exception as e:
                err_msg = str(e)
                record.zoho_status = "FAILED"
                record.zoho_error = err_msg
                
                # Write to Audit Log
                audit = models.ZohoAuditLog(
                    session_id=session_id,
                    excel_row=record.original_row_number,
                    amount=record.amount or 0.0,
                    description=record.description or "",
                    destination_report=report_names.get(report_id, f"Report {report_id}"),
                    result="FAILED",
                    error_details=err_msg
                )
                db.add(audit)
                db.commit()
                
                # Check for global connectivity/revocation/auth failures to halt the loop safely
                is_global_err = any(phrase in err_msg.lower() for phrase in [
                    "revoked", "invalid_grant", "unauthorized", "conn connection is invalid",
                    "not authorized to perform", "oauth", "network error"
                ])
                if is_global_err:
                    logger.error(f"Global connection failure detected: {err_msg}. Aborting remaining rows.")
                    # Mark all other CREATING/PENDING rows in this batch back to PENDING so they can resume
                    for p in records:
                        if p.zoho_status in ["PENDING", "CREATING"]:
                            p.zoho_status = "PENDING"
                            p.zoho_error = "Aborted due to global connection/oauth failure."
                    session.status = "Failed"
                    db.commit()
                    return

        # Determine final status of session
        has_failed = db.query(models.ExpenseRecord).filter(
            models.ExpenseRecord.session_id == session_id,
            models.ExpenseRecord.zoho_status == "FAILED"
        ).first() is not None
        
        has_pending = db.query(models.ExpenseRecord).filter(
            models.ExpenseRecord.session_id == session_id,
            models.ExpenseRecord.zoho_status == "PENDING"
        ).first() is not None
        
        if has_failed:
            session.status = "Errors"
        elif has_pending:
            session.status = "Validated"
        else:
            session.status = "Completed"
            
        db.commit()
        logger.info(f"Bulk creation complete for session {session_id}.")
        
    except Exception as ex:
        logger.exception(f"Unexpected error in bulk processor background task: {ex}")
        try:
            session.status = "Failed"
            db.commit()
        except Exception:
            pass
    finally:
        if should_close:
            db.close()
