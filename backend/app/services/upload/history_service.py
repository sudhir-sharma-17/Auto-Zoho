from sqlalchemy.orm import Session
from typing import List, Dict, Any, Optional
from app.database import models

def create_upload_session(
    db: Session,
    file_name: str,
    total_rows: int,
    valid_rows: int,
    invalid_rows: int,
    gst_count: int,
    nongst_count: int,
    status: str,
    error_report_path: Optional[str] = None
) -> models.UploadSession:
    """
    Creates and logs a new validation session record.
    """
    import datetime
    today_str = datetime.date.today().strftime("%Y%m%d")
    prefix = f"UP-{today_str}-"
    
    # Calculate today's session sequence
    count = db.query(models.UploadSession).filter(
        models.UploadSession.upload_session_id.like(f"{prefix}%")
    ).count()
    session_seq = count + 1
    upload_session_id = f"{prefix}{session_seq:03d}"

    db_session = models.UploadSession(
        file_name=file_name,
        total_rows=total_rows,
        valid_rows=valid_rows,
        invalid_rows=invalid_rows,
        gst_count=gst_count,
        nongst_count=nongst_count,
        status=status,
        error_report_path=error_report_path,
        upload_session_id=upload_session_id
    )
    db.add(db_session)
    db.commit()
    db.refresh(db_session)
    return db_session

def add_expense_records(
    db: Session,
    session_id: int,
    records: List[Dict[str, Any]]
) -> List[models.ExpenseRecord]:
    """
    Saves parsed expense records associated with an upload session.
    """
    import datetime
    db_records = []
    now = datetime.datetime.utcnow()
    for rec in records:
        db_rec = models.ExpenseRecord(
            session_id=session_id,
            original_row_number=rec.get("original_row_number"),
            expense_date=rec.get("expense_date"),
            amount=rec.get("amount"),
            description=rec.get("description"),
            gst_type=rec.get("gst_type"),
            category=rec.get("category"),
            tax_type=rec.get("tax_type"),
            paid_through=rec.get("paid_through"),
            project=rec.get("project"),
            expense_kind=rec.get("expense_kind"),
            vendor_name=rec.get("vendor_name"),
            status=rec.get("status"),
            errors=rec.get("errors"),
            created_at=now,
            updated_at=now
        )
        db.add(db_rec)
        db_records.append(db_rec)
    db.commit()
    return db_records

def get_all_sessions(db: Session) -> List[models.UploadSession]:
    """
    Returns list of all sessions, ordered by most recent.
    """
    return db.query(models.UploadSession).order_by(models.UploadSession.timestamp.desc()).all()

def get_session_by_id(db: Session, session_id: int) -> Optional[models.UploadSession]:
    """
    Fetches a specific validation session by its ID.
    """
    return db.query(models.UploadSession).filter(models.UploadSession.id == session_id).first()

def get_session_records(
    db: Session,
    session_id: int,
    status_filter: Optional[str] = None,
    gst_filter: Optional[str] = None,
    search_query: Optional[str] = None
) -> List[models.ExpenseRecord]:
    """
    Fetches expense rows matching status, GST, or textual search tags.
    """
    query = db.query(models.ExpenseRecord).filter(models.ExpenseRecord.session_id == session_id)
    
    if status_filter:
        query = query.filter(models.ExpenseRecord.status == status_filter.upper())
        
    if gst_filter:
        query = query.filter(models.ExpenseRecord.gst_type == gst_filter.upper())
        
    if search_query:
        search_pattern = f"%{search_query}%"
        query = query.filter(
            models.ExpenseRecord.description.like(search_pattern) |
            models.ExpenseRecord.category.like(search_pattern) |
            models.ExpenseRecord.vendor_name.like(search_pattern) |
            models.ExpenseRecord.project.like(search_pattern)
        )
        
    return query.order_by(models.ExpenseRecord.original_row_number.asc()).all()

def delete_session(db: Session, session_id: int) -> bool:
    """
    Deletes a specific validation session, its cascading records,
    and associated files on disk (error reports and processed uploads).
    """
    import os
    db_session = db.query(models.UploadSession).filter(models.UploadSession.id == session_id).first()
    if not db_session:
        return False
        
    # Clean up error report file on disk
    if db_session.error_report_path and os.path.exists(db_session.error_report_path):
        try:
            os.remove(db_session.error_report_path)
        except Exception as e:
            print(f"Error removing error report file: {e}")
            
    # Clean up processed upload spreadsheet on disk
    from app.config.config import settings
    processed_dir = os.path.join(settings.UPLOAD_DIR, "processed")
    if os.path.exists(processed_dir):
        for fname in os.listdir(processed_dir):
            if fname.startswith(f"session_{session_id}_"):
                try:
                    os.remove(os.path.join(processed_dir, fname))
                except Exception as e:
                    print(f"Error removing processed file: {e}")

    db.delete(db_session)
    db.commit()
    return True

def clear_all_history(db: Session):
    """
    Deletes all validation sessions, all cascading records, and clears associated folders.
    """
    import os
    import shutil
    from app.config.config import settings

    # Clean folders on disk
    for folder in ["error_reports", "processed", "temp"]:
        path = os.path.join(settings.UPLOAD_DIR, folder)
        if os.path.exists(path):
            for filename in os.listdir(path):
                file_filepath = os.path.join(path, filename)
                try:
                    if os.path.isfile(file_filepath) or os.path.islink(file_filepath):
                        os.unlink(file_filepath)
                    elif os.path.isdir(file_filepath):
                        shutil.rmtree(file_filepath)
                except Exception as e:
                    print(f"Error cleaning {file_filepath}: {e}")

    # Delete all session records (cascades to expense_records)
    db.query(models.UploadSession).delete()
    db.commit()
