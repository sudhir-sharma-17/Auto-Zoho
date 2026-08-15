import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship

from app.database.session import Base

class UploadSession(Base):
    __tablename__ = "upload_sessions"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    file_name = Column(String(255), nullable=False)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    total_rows = Column(Integer, default=0, nullable=False)
    valid_rows = Column(Integer, default=0, nullable=False)
    invalid_rows = Column(Integer, default=0, nullable=False)
    gst_count = Column(Integer, default=0, nullable=False)
    nongst_count = Column(Integer, default=0, nullable=False)
    status = Column(String(50), nullable=False)  # "Validated", "Errors", "Failed"
    error_report_path = Column(String(500), nullable=True)
    upload_session_id = Column(String(50), unique=True, index=True, nullable=True)
    selected_gst_report_id = Column(String(100), nullable=True)
    selected_nongst_report_id = Column(String(100), nullable=True)
    mapping_snapshot = Column(Text, nullable=True)

    # Relationships
    records = relationship("ExpenseRecord", back_populates="session", cascade="all, delete-orphan")

class ExpenseRecord(Base):
    __tablename__ = "expense_records"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    session_id = Column(Integer, ForeignKey("upload_sessions.id", ondelete="CASCADE"), nullable=False)
    original_row_number = Column(Integer, nullable=False)
    
    # Business Columns
    expense_date = Column(String(100), nullable=True)
    amount = Column(Float, nullable=True)
    description = Column(Text, nullable=True)
    gst_type = Column(String(50), nullable=True)  # "GST", "NON_GST", "UNKNOWN"
    category = Column(String(255), nullable=True)
    tax_type = Column(String(255), nullable=True)
    paid_through = Column(String(255), nullable=True)
    project = Column(String(255), nullable=True)
    expense_kind = Column(String(255), nullable=True)
    vendor_name = Column(String(255), nullable=True)
    
    # Status and validation feedback
    status = Column(String(50), nullable=False)  # "VALID", "INVALID"
    errors = Column(Text, nullable=True)  # Semicolon-separated errors or JSON list of errors
    
    # Zoho Upload status
    zoho_status = Column(String(50), nullable=True, default="PENDING")
    zoho_expense_id = Column(String(100), nullable=True)
    zoho_error = Column(Text, nullable=True)
    destination_report_id = Column(String(100), nullable=True)
    error_code = Column(String(100), nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=True)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow, nullable=True)

    session = relationship("UploadSession", back_populates="records")

class ZohoCredential(Base):
    __tablename__ = "zoho_credentials"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    api_domain = Column(String(255), nullable=False)  # e.g., https://www.zohoapis.com
    encrypted_access_token = Column(Text, nullable=False)
    encrypted_refresh_token = Column(Text, nullable=False)
    expires_at = Column(DateTime, nullable=False)  # Expiration timestamp (UTC)
    organization_id = Column(String(100), nullable=True)
    organization_name = Column(String(255), nullable=True)
    scopes = Column(String(500), default="", nullable=True)  # space-separated or comma-separated scopes
    connected_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)

class PendingState(Base):
    __tablename__ = "pending_oauth_states"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    state = Column(String(100), unique=True, index=True, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)

class ZohoAuditLog(Base):
    __tablename__ = "zoho_audit_logs"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    session_id = Column(Integer, nullable=True)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    excel_row = Column(Integer, nullable=False)
    amount = Column(Float, nullable=False)
    description = Column(String(500), nullable=False)
    destination_report = Column(String(255), nullable=False)
    result = Column(String(50), nullable=False)  # "SUCCESS" or "FAILED"
    zoho_expense_id = Column(String(100), nullable=True)
    error_details = Column(Text, nullable=True)

class AppLockConfig(Base):
    __tablename__ = "app_lock_configs"
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    hashed_pin = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
