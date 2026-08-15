from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime

class ExpenseRecordBase(BaseModel):
    original_row_number: int
    expense_date: Optional[str] = None
    amount: Optional[float] = None
    description: Optional[str] = None
    gst_type: Optional[str] = None
    category: Optional[str] = None
    tax_type: Optional[str] = None
    paid_through: Optional[str] = None
    project: Optional[str] = None
    expense_kind: Optional[str] = None
    vendor_name: Optional[str] = None
    status: str
    errors: Optional[str] = None

class ExpenseRecordOut(ExpenseRecordBase):
    id: int
    session_id: int

    class Config:
        from_attributes = True

class UploadSessionBase(BaseModel):
    file_name: str
    total_rows: int
    valid_rows: int
    invalid_rows: int
    gst_count: int
    nongst_count: int
    status: str

class UploadSessionOut(UploadSessionBase):
    id: int
    timestamp: datetime
    error_report_path: Optional[str] = None

    class Config:
        from_attributes = True

class UploadSessionDetailOut(UploadSessionOut):
    records: List[ExpenseRecordOut]

    class Config:
        from_attributes = True

# Response for validation endpoint
class ExcelValidationResponse(BaseModel):
    session: UploadSessionOut
    records: List[ExpenseRecordOut]
    message: str
