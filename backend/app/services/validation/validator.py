import re
import datetime
from typing import List, Dict, Any, Tuple, Optional

REQUIRED_COLUMNS = [
    "Expense Date",
    "Amount",
    "Description",
    "GST/Non GST",
    "Category",
    "Tax Type",
    "Paid Through",
    "Project",
    "Expense Kind",
    "Vendor Name"
]

def normalize_gst(val: Any) -> Tuple[Optional[str], bool]:
    """
    Normalizes GST/Non GST values.
    Returns:
        (normalized_value, is_valid)
    """
    if val is None or str(val).strip() == "":
        return None, False
        
    s = str(val).strip().upper()
    
    # Matches GST, gst, GST (with spaces)
    if s == "GST":
        return "GST", True
        
    # Matches NON GST, NON-GST, non gst, etc.
    normalized_nongst = re.sub(r'[^A-Z]', '', s)
    if normalized_nongst in ["NONGST", "NON_GST"]:
        return "NON_GST", True
        
    # Check if text contains non-gst variations
    if "NON GST" in s or "NON-GST" in s or "NON_GST" in s:
        return "NON_GST", True
        
    return s, False

def parse_excel_date(val: Any) -> Tuple[Optional[str], Optional[str]]:
    """
    Attempts to parse Excel dates (which can be datetime objects, serial numbers, or string formats).
    Returns (formatted_date_string, error_message)
    """
    if val is None or str(val).strip() == "":
        return None, "Expense Date is required"
        
    # If already a datetime or date object
    if isinstance(val, (datetime.datetime, datetime.date)):
        return val.strftime("%Y-%m-%d"), None
        
    # If it is a string representation of datetime
    val_str = str(val).strip()
    
    # Check if numeric (Excel serial date)
    try:
        if val_str.isdigit() or (val_str.replace('.', '', 1).isdigit() and '.' in val_str):
            serial_num = float(val_str)
            # Excel leap year bug: Excel thinks 1900 was a leap year
            if serial_num < 60:
                base_date = datetime.date(1899, 12, 31)
            else:
                base_date = datetime.date(1899, 12, 30)
            parsed_date = base_date + datetime.timedelta(days=serial_num)
            return parsed_date.strftime("%Y-%m-%d"), None
    except Exception:
        pass

    # Common string formats to parse
    date_formats = [
        "%Y-%m-%d", "%Y-%m-%d %H:%M:%S",
        "%d/%m/%Y", "%d/%m/%y",
        "%m/%d/%Y", "%m/%d/%y",
        "%d-%m-%Y", "%d-%m-%y"
    ]
    
    for fmt in date_formats:
        try:
            parsed = datetime.datetime.strptime(val_str, fmt)
            return parsed.strftime("%Y-%m-%d"), None
        except ValueError:
            continue
            
    return val_str, f"Invalid date format: '{val_str}'"

def validate_excel_columns(columns: List[str]) -> List[str]:
    """
    Verifies that all required columns are present in the list of spreadsheet columns.
    Returns a list of missing columns (empty if all are present).
    """
    missing = []
    for col in REQUIRED_COLUMNS:
        if col not in columns:
            missing.append(col)
    return missing

def validate_expense_row(row: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validates a single row and adds standard feedback.
    """
    errors = []
    validated_row = row.copy()
    
    # 1. Expense Date
    date_raw = row.get("Expense Date")
    date_str, date_err = parse_excel_date(date_raw)
    if date_err:
        errors.append(date_err)
    validated_row["Expense Date"] = date_str if date_str else date_raw
    
    # 2. Amount
    amount_raw = row.get("Amount")
    amount_val = None
    if amount_raw is None or str(amount_raw).strip() == "":
        errors.append("Amount is required")
    else:
        try:
            # Strip currency symbols if present (e.g. ₹, $)
            cleaned_amount = re.sub(r'[^\d\.\-]', '', str(amount_raw))
            amount_val = float(cleaned_amount)
            if amount_val < 0:
                errors.append("Amount cannot be negative")
        except ValueError:
            errors.append("Amount must be numeric")
            
    validated_row["Amount"] = amount_val if amount_val is not None else amount_raw
    
    # 3. Description
    desc = row.get("Description")
    if desc is None or str(desc).strip() == "":
        errors.append("Description is required")
    else:
        validated_row["Description"] = str(desc).strip()
        
    # 4. GST/Non GST
    gst_raw = row.get("GST/Non GST")
    gst_norm, gst_ok = normalize_gst(gst_raw)
    if gst_raw is None or str(gst_raw).strip() == "":
        errors.append("GST/Non GST value is required")
    elif not gst_ok:
        errors.append(f"Invalid GST/Non GST value: '{gst_raw}'")
    validated_row["GST/Non GST"] = gst_norm
    
    # 5-10. Simple required columns
    required_text_cols = [
        ("Category", "Category is required"),
        ("Tax Type", "Tax Type is required"),
        ("Paid Through", "Paid Through is required"),
        ("Project", "Project is required"),
        ("Expense Kind", "Expense Kind is required"),
        ("Vendor Name", "Vendor Name is required")
    ]
    
    for key, err_msg in required_text_cols:
        val = row.get(key)
        if val is None or str(val).strip() == "":
            errors.append(err_msg)
        else:
            validated_row[key] = str(val).strip()

    # Determine validation status
    if errors:
        validated_row["_status"] = "INVALID"
        validated_row["_errors"] = "; ".join(errors)
    else:
        validated_row["_status"] = "VALID"
        validated_row["_errors"] = None
        
    return validated_row
