import os
import shutil
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from typing import List, Optional

from app.database.session import get_db
from app.schemas import schemas
from app.services.excel import parser
from app.services.validation import validator, report_generator
from app.services.upload import history_service
from app.config.config import settings
from app.api.deps import get_current_admin

router = APIRouter()


import sqlalchemy

@router.get("/health")
def health_check(db: Session = Depends(get_db)):
    """Health check endpoint verifying application and database availability."""
    try:
        db.execute(sqlalchemy.text("SELECT 1"))
        return {"status": "healthy", "database": "connected"}
    except Exception:
        return JSONResponse(
            status_code=503,
            content={"status": "unhealthy", "database": "disconnected"}
        )

@router.post("/excel/validate", response_model=schemas.ExcelValidationResponse)
def validate_excel(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    admin: any = Depends(get_current_admin)
):
    """
    Uploads, parses, and validates an Excel spreadsheet.
    Logs results in the SQLite database and exports error reports if formatting rules fail.
    """
    if not (file.filename.endswith(".xlsx") or file.filename.endswith(".xls")):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported file format. Please upload an Excel spreadsheet (.xlsx or .xls)."
        )

    # Make a temporary directory to save the file
    temp_dir = os.path.join(settings.UPLOAD_DIR, "temp")
    os.makedirs(temp_dir, exist_ok=True)
    
    file_path = os.path.join(temp_dir, file.filename)
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    try:
        # Parse spreadsheet
        raw_records = parser.parse_excel_file(file_path)
    except Exception as e:
        if os.path.exists(file_path):
            os.remove(file_path)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to read workbook: {str(e)}"
        )

    # If the sheet is empty
    if not raw_records:
        if os.path.exists(file_path):
            os.remove(file_path)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The uploaded file contains no data rows."
        )

    # Perform structural validation
    columns = list(raw_records[0].keys())
    # Exclude internal metadata key '_row_number'
    columns = [col for col in columns if col != '_row_number']
    
    missing_cols = validator.validate_excel_columns(columns)
    if missing_cols:
        if os.path.exists(file_path):
            os.remove(file_path)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "message": "Required columns are missing from the spreadsheet.",
                "missing_columns": missing_cols
            }
        )

    # Process and validate row level data
    validated_records = []
    gst_count = 0
    nongst_count = 0
    invalid_rows = 0
    valid_rows = 0

    for raw_rec in raw_records:
        validated_rec = validator.validate_expense_row(raw_rec)
        
        # Accumulate metrics
        if validated_rec["_status"] == "VALID":
            valid_rows += 1
        else:
            invalid_rows += 1

        # Count normalized GST types
        if validated_rec["GST/Non GST"] == "GST":
            gst_count += 1
        elif validated_rec["GST/Non GST"] == "NON_GST":
            nongst_count += 1
            
        validated_records.append(validated_rec)

    # Determine validation status
    session_status = "Validated" if invalid_rows == 0 else "Errors"

    # Create the database session
    db_session = history_service.create_upload_session(
        db=db,
        file_name=file.filename,
        total_rows=len(validated_records),
        valid_rows=valid_rows,
        invalid_rows=invalid_rows,
        gst_count=gst_count,
        nongst_count=nongst_count,
        status=session_status
    )

    # Generate and save error report if invalid rows exist
    error_report_relative_path = None
    if invalid_rows > 0:
        reports_dir = os.path.join(settings.UPLOAD_DIR, "error_reports")
        os.makedirs(reports_dir, exist_ok=True)
        report_file_name = f"errors_session_{db_session.id}.xlsx"
        report_absolute_path = os.path.join(reports_dir, report_file_name)
        
        invalid_only = [rec for rec in validated_records if rec["_status"] == "INVALID"]
        
        # Map fields to database records format for report generator
        mapped_invalid = []
        for idx, rec in enumerate(invalid_only):
            mapped_invalid.append({
                "original_row_number": rec.get("_row_number"),
                "expense_date": rec.get("Expense Date"),
                "amount": rec.get("Amount"),
                "description": rec.get("Description"),
                "gst_type": rec.get("GST/Non GST"),
                "category": rec.get("Category"),
                "tax_type": rec.get("Tax Type"),
                "paid_through": rec.get("Paid Through"),
                "project": rec.get("Project"),
                "expense_kind": rec.get("Expense Kind"),
                "vendor_name": rec.get("Vendor Name"),
                "errors": rec.get("_errors")
            })
            
        report_generator.generate_error_excel(mapped_invalid, report_absolute_path)
        # Store path relative to workspace or upload root for simpler downloads
        db_session.error_report_path = report_absolute_path
        db.commit()

    # Move processed file to storage
    final_storage_dir = os.path.join(settings.UPLOAD_DIR, "processed")
    os.makedirs(final_storage_dir, exist_ok=True)
    shutil.move(file_path, os.path.join(final_storage_dir, f"session_{db_session.id}_{file.filename}"))

    # Map validation objects to DB records format
    db_records_to_insert = []
    for rec in validated_records:
        db_records_to_insert.append({
            "original_row_number": rec.get("_row_number"),
            "expense_date": rec.get("Expense Date"),
            "amount": rec.get("Amount"),
            "description": rec.get("Description"),
            "gst_type": rec.get("GST/Non GST") or "UNKNOWN",
            "category": rec.get("Category"),
            "tax_type": rec.get("Tax Type"),
            "paid_through": rec.get("Paid Through"),
            "project": rec.get("Project"),
            "expense_kind": rec.get("Expense Kind"),
            "vendor_name": rec.get("Vendor Name"),
            "status": rec.get("_status"),
            "errors": rec.get("_errors")
        })

    db_records = history_service.add_expense_records(db, db_session.id, db_records_to_insert)

    return {
        "session": db_session,
        "records": db_records,
        "message": f"Successfully parsed {db_session.total_rows} rows."
    }

@router.get("/uploads/history", response_model=List[schemas.UploadSessionOut])
def get_history(db: Session = Depends(get_db), admin: any = Depends(get_current_admin)):
    """Fetches all past upload validation sessions."""
    return history_service.get_all_sessions(db)

@router.delete("/uploads/history")
def clear_history(db: Session = Depends(get_db), admin: any = Depends(get_current_admin)):
    """Deletes all validation sessions and clears history completely."""
    history_service.clear_all_history(db)
    return {"status": "success", "message": "All validation history has been cleared."}

@router.delete("/uploads/{session_id}")
def delete_session(session_id: int, db: Session = Depends(get_db), admin: any = Depends(get_current_admin)):
    """Deletes a specific validation session and its database records."""
    success = history_service.delete_session(db, session_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Upload session ID {session_id} not found."
        )
    return {"status": "success", "message": f"Session {session_id} successfully deleted."}

@router.get("/uploads/{session_id}", response_model=schemas.UploadSessionDetailOut)
def get_session_details(
    session_id: int,
    status_filter: Optional[str] = Query(None, alias="status"),
    gst_filter: Optional[str] = Query(None, alias="gst"),
    search_query: Optional[str] = Query(None, alias="search"),
    db: Session = Depends(get_db),
    admin: any = Depends(get_current_admin)
):
    """
    Fetches details of a specific validation session,
    allowing text searching and column filtering.
    """
    session_info = history_service.get_session_by_id(db, session_id)
    if not session_info:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Upload session ID {session_id} not found."
        )

    records = history_service.get_session_records(
        db=db,
        session_id=session_id,
        status_filter=status_filter,
        gst_filter=gst_filter,
        search_query=search_query
    )

    # Construct detail payload manually to inject filtered records
    return {
        "id": session_info.id,
        "file_name": session_info.file_name,
        "timestamp": session_info.timestamp,
        "total_rows": session_info.total_rows,
        "valid_rows": session_info.valid_rows,
        "invalid_rows": session_info.invalid_rows,
        "gst_count": session_info.gst_count,
        "nongst_count": session_info.nongst_count,
        "status": session_info.status,
        "error_report_path": session_info.error_report_path,
        "records": records
    }

@router.get("/uploads/{session_id}/errors")
def download_error_report(session_id: int, db: Session = Depends(get_db), admin: any = Depends(get_current_admin)):
    """Downloads the Excel report containing invalid rows for this session."""
    session_info = history_service.get_session_by_id(db, session_id)
    if not session_info:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Upload session ID {session_id} not found."
        )
        
    if not session_info.error_report_path or not os.path.exists(session_info.error_report_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No error report spreadsheet is available for this session."
        )
        
    return FileResponse(
        path=session_info.error_report_path,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=f"error_report_{session_info.file_name}"
    )

from pydantic import BaseModel

class PinSetupPayload(BaseModel):
    pin: str

class PinVerifyPayload(BaseModel):
    pin: str

@router.get("/lock/status")
def get_lock_status(db: Session = Depends(get_db), admin: any = Depends(get_current_admin)):
    from app.database import models
    config = db.query(models.AppLockConfig).first()
    has_pin = config is not None and config.hashed_pin is not None
    return {"has_pin": has_pin}

@router.post("/lock/setup")
def setup_pin(payload: PinSetupPayload, db: Session = Depends(get_db), admin: any = Depends(get_current_admin)):
    from app.database import models
    from app.security.encryption import hash_pin
    config = db.query(models.AppLockConfig).first()
    hashed = hash_pin(payload.pin)
    if not config:
        config = models.AppLockConfig(hashed_pin=hashed)
        db.add(config)
    else:
        config.hashed_pin = hashed
    db.commit()
    return {"status": "success", "message": "PIN setup successful."}

@router.post("/lock/verify")
def verify_app_pin(payload: PinVerifyPayload, db: Session = Depends(get_db), admin: any = Depends(get_current_admin)):
    from app.database import models
    from app.security.encryption import verify_pin
    config = db.query(models.AppLockConfig).first()
    if not config or not config.hashed_pin:
        return {"verified": True}
    
    verified = verify_pin(payload.pin, config.hashed_pin)
    if not verified:
        raise HTTPException(status_code=400, detail="Incorrect PIN.")
    return {"verified": True}

@router.post("/lock/disable")
def disable_pin(payload: PinVerifyPayload, db: Session = Depends(get_db), admin: any = Depends(get_current_admin)):
    from app.database import models
    from app.security.encryption import verify_pin
    config = db.query(models.AppLockConfig).first()
    if not config or not config.hashed_pin:
        return {"status": "success", "message": "PIN not configured."}
    
    verified = verify_pin(payload.pin, config.hashed_pin)
    if not verified:
        raise HTTPException(status_code=400, detail="Incorrect PIN.")
        
    config.hashed_pin = None
    db.commit()
    return {"status": "success", "message": "PIN disabled."}
