import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../backend')))

import pytest
from tests.generate_test_excel import create_sample_excel
from app.services.excel.parser import parse_excel_file
from app.services.validation.validator import (
    normalize_gst,
    parse_excel_date,
    validate_excel_columns,
    validate_expense_row
)
from app.services.validation.report_generator import generate_error_excel

# Setup sample dataset path
SAMPLE_EXCEL_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "Sample dataset.xlsx"))

@pytest.fixture(scope="session", autouse=True)
def setup_test_excel():
    """Generates the mock spreadsheet before testing begins."""
    create_sample_excel(SAMPLE_EXCEL_PATH)
    yield
    # Clean up test sheet if desired (optional)
    if os.path.exists(SAMPLE_EXCEL_PATH):
        try:
            os.remove(SAMPLE_EXCEL_PATH)
        except OSError:
            pass

def test_excel_parsing():
    """Confirms that pandas successfully loads 19 spreadsheet rows and tracks original row numbers."""
    records = parse_excel_file(SAMPLE_EXCEL_PATH)
    assert len(records) == 19
    
    # Assert row numbers are 1-indexed Excel numbers (starting at 2 for first data row)
    assert records[0]["_row_number"] == 2
    assert records[18]["_row_number"] == 20

def test_column_validation():
    """Ensures missing headers are successfully reported and normal headers pass."""
    valid_cols = [
        "Expense Date", "Amount", "Description", "GST/Non GST", 
        "Category", "Tax Type", "Paid Through", "Project", 
        "Expense Kind", "Vendor Name"
    ]
    missing = validate_excel_columns(valid_cols)
    assert len(missing) == 0

    invalid_cols = ["Expense Date", "Amount", "Description"]
    missing = validate_excel_columns(invalid_cols)
    assert "Vendor Name" in missing
    assert "Tax Type" in missing

def test_gst_normalization():
    """Tests GST input variations to ensure standard codes result."""
    # Test valid GST variants
    assert normalize_gst("GST") == ("GST", True)
    assert normalize_gst("gst") == ("GST", True)
    assert normalize_gst(" Gst ") == ("GST", True)

    # Test valid Non-GST variants
    assert normalize_gst("NON GST") == ("NON_GST", True)
    assert normalize_gst("NON-GST") == ("NON_GST", True)
    assert normalize_gst("non gst") == ("NON_GST", True)
    assert normalize_gst("non-gst") == ("NON_GST", True)
    assert normalize_gst("Non GST") == ("NON_GST", True)
    assert normalize_gst("NON_GST") == ("NON_GST", True)

    # Test invalid values
    norm, ok = normalize_gst("ABC")
    assert not ok
    assert norm == "ABC"

    norm, ok = normalize_gst("")
    assert not ok
    assert norm is None

def test_date_parsing():
    """Checks parsing dates from strings, datetimes, and Excel numeric values."""
    # String dates
    d, err = parse_excel_date("2026-07-31")
    assert d == "2026-07-31" and err is None

    d, err = parse_excel_date("31/07/26")
    assert d == "2026-07-31" and err is None

    # Excel serial number (46138 -> 2026-04-26)
    d, err = parse_excel_date(46138)
    assert d == "2026-04-26" and err is None

    # Invalid string
    d, err = parse_excel_date("invalid-date")
    assert err is not None

def test_row_validations():
    """Validates row-level rules for amounts, vendors, dates, and duplicate rows."""
    records = parse_excel_file(SAMPLE_EXCEL_PATH)
    
    # Row 1 (Index 0): Valid masking tape
    res = validate_expense_row(records[0])
    assert res["_status"] == "VALID"
    assert res["_errors"] is None
    assert res["GST/Non GST"] == "GST"

    # Row 2 & 3 (Index 1 & 2): Duplicate rows check
    res2 = validate_expense_row(records[1])
    res3 = validate_expense_row(records[2])
    assert res2["_status"] == "VALID"
    assert res3["_status"] == "VALID"
    # Ensure they remain independent records and are not merged
    assert res2["_row_number"] == 3
    assert res3["_row_number"] == 4

    # Row 16 (Index 15): Invalid GST ("ABC")
    res16 = validate_expense_row(records[15])
    assert res16["_status"] == "INVALID"
    assert "Invalid GST/Non GST value" in res16["_errors"]

    # Row 17 (Index 16): Missing Amount
    res17 = validate_expense_row(records[16])
    assert res17["_status"] == "INVALID"
    assert "Amount is required" in res17["_errors"]

    # Row 18 (Index 17): Missing Vendor
    res18 = validate_expense_row(records[17])
    assert res18["_status"] == "INVALID"
    assert "Vendor Name is required" in res18["_errors"]

    # Row 19 (Index 18): Negative Amount & Invalid Date
    res19 = validate_expense_row(records[18])
    assert res19["_status"] == "INVALID"
    assert "Amount cannot be negative" in res19["_errors"]
    assert "Invalid date format" in res19["_errors"]

def test_error_report_generation():
    """Ensures error report exports write spreadsheet files correctly with failure reasons."""
    records = parse_excel_file(SAMPLE_EXCEL_PATH)
    invalid_rows = []
    
    for rec in records:
        val_rec = validate_expense_row(rec)
        if val_rec["_status"] == "INVALID":
            invalid_rows.append({
                "original_row_number": val_rec["_row_number"],
                "expense_date": val_rec["Expense Date"],
                "amount": val_rec["Amount"],
                "description": val_rec["Description"],
                "gst_type": val_rec["GST/Non GST"],
                "category": val_rec["Category"],
                "tax_type": val_rec["Tax Type"],
                "paid_through": val_rec["Paid Through"],
                "project": val_rec["Project"],
                "expense_kind": val_rec["Expense Kind"],
                "vendor_name": val_rec["Vendor Name"],
                "errors": val_rec["_errors"]
            })
            
    assert len(invalid_rows) == 4
    
    report_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "Error report test.xlsx"))
    if os.path.exists(report_path):
        os.remove(report_path)
        
    generate_error_excel(invalid_rows, report_path)
    assert os.path.exists(report_path)
    
    # Clean up error file
    try:
        os.remove(report_path)
    except OSError:
        pass
