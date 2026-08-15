import pandas as pd
from typing import List, Dict, Any

def generate_error_excel(invalid_records: List[Dict[str, Any]], output_path: str):
    """
    Creates an Excel spreadsheet containing only rows that failed validation.
    Columns included:
      - Original Row
      - Expense Date
      - Amount
      - Description
      - GST/Non GST
      - Category
      - Tax Type
      - Paid Through
      - Project
      - Expense Kind
      - Vendor Name
      - Error Reason
    """
    rows_data = []
    for rec in invalid_records:
        rows_data.append({
            "Original Row": rec.get("original_row_number"),
            "Expense Date": rec.get("expense_date"),
            "Amount": rec.get("amount"),
            "Description": rec.get("description"),
            "GST/Non GST": rec.get("gst_type"),
            "Category": rec.get("category"),
            "Tax Type": rec.get("tax_type"),
            "Paid Through": rec.get("paid_through"),
            "Project": rec.get("project"),
            "Expense Kind": rec.get("expense_kind"),
            "Vendor Name": rec.get("vendor_name"),
            "Error Reason": rec.get("errors")
        })
        
    df = pd.DataFrame(rows_data)
    
    # Save the dataframe using openpyxl engine
    df.to_excel(output_path, index=False, engine="openpyxl")
