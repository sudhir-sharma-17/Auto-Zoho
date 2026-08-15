import os
import pandas as pd

def create_sample_excel(output_path: str):
    """
    Generates a spreadsheet with the exact layout specified in Section 9.
    Contains:
      - 19 rows total
      - 11 GST rows (with different variations to check normalization)
      - 8 NON-GST rows (with different variations to check normalization)
      - Duplicate rows (to verify they are preserved and not merged)
      - Invalid rows (empty vendor, negative amount, invalid date, bad GST text)
    """
    data = [
        # Valid GST rows (1-5)
        {
            "Sl.No": 1, "Expense Date": "2026-07-31", "Amount": 210, "Description": "Masking Tape",
            "GST/Non GST": "GST", "Category": "Hardware", "Tax Type": "GST 18%", "Paid Through": "Petty Cash",
            "Project": "Client Alpha", "Expense Kind": "Goods", "Vendor Name": "Raj Traders", "Remark": "Ignored remark"
        },
        {
            "Sl.No": 2, "Expense Date": "31/07/26", "Amount": 500, "Description": "Hardware fitting",
            "GST/Non GST": "gst", "Category": "Project", "Tax Type": "GST 18%", "Paid Through": "Credit Card",
            "Project": "Client Beta", "Expense Kind": "Services", "Vendor Name": "BuildMart", "Remark": "Ignored"
        },
        # Duplicate row of above (to test duplicate preservation)
        {
            "Sl.No": 3, "Expense Date": "31/07/26", "Amount": 500, "Description": "Hardware fitting",
            "GST/Non GST": "gst", "Category": "Project", "Tax Type": "GST 18%", "Paid Through": "Credit Card",
            "Project": "Client Beta", "Expense Kind": "Services", "Vendor Name": "BuildMart", "Remark": "Ignored"
        },
        {
            "Sl.No": 4, "Expense Date": "2026-08-01", "Amount": "1500.50", "Description": "Office Lunch",
            "GST/Non GST": " GST ", "Category": "Meals & Entertainment", "Tax Type": "GST 5%", "Paid Through": "Petty Cash",
            "Project": "Internal Office", "Expense Kind": "Services", "Vendor Name": "Star Hotel", "Remark": "Lunch"
        },
        {
            "Sl.No": 5, "Expense Date": 46138, "Amount": 12000, "Description": "Laptops repair",  # Serial date (excel)
            "GST/Non GST": "Gst", "Category": "Repairs", "Tax Type": "GST 18%", "Paid Through": "Bank Account",
            "Project": "Client Gamma", "Expense Kind": "Services", "Vendor Name": "SysTech", "Remark": "Hinge repair"
        },
        
        # Valid NON-GST rows (6-10)
        {
            "Sl.No": 6, "Expense Date": "2026-08-02", "Amount": 150, "Description": "Local transport auto",
            "GST/Non GST": "NON-GST", "Category": "Travel", "Tax Type": "Out of Scope", "Paid Through": "Petty Cash",
            "Project": "Client Alpha", "Expense Kind": "Services", "Vendor Name": "Auto Driver", "Remark": "Auto ride"
        },
        {
            "Sl.No": 7, "Expense Date": "2026-08-02", "Amount": 300, "Description": "Courier envelopes",
            "GST/Non GST": "NON GST", "Category": "Postage", "Tax Type": "Out of Scope", "Paid Through": "Petty Cash",
            "Project": "Internal Office", "Expense Kind": "Goods", "Vendor Name": "BlueDart", "Remark": "Envelopes"
        },
        {
            "Sl.No": 8, "Expense Date": "2026-08-03", "Amount": 450, "Description": "Office stationeries",
            "GST/Non GST": "non gst", "Category": "Printing & Stationery", "Tax Type": "Zero Rated", "Paid Through": "Petty Cash",
            "Project": "Internal Office", "Expense Kind": "Goods", "Vendor Name": "Local Book Depot", "Remark": ""
        },
        {
            "Sl.No": 9, "Expense Date": "2026-08-03", "Amount": 200, "Description": "Tea and snacks",
            "GST/Non GST": "non-gst", "Category": "Meals & Entertainment", "Tax Type": "Out of Scope", "Paid Through": "Petty Cash",
            "Project": "Internal Office", "Expense Kind": "Goods", "Vendor Name": "Snack Corner", "Remark": ""
        },
        {
            "Sl.No": 10, "Expense Date": "2026-08-04", "Amount": 90, "Description": "Photocopying plans",
            "GST/Non GST": "Non GST", "Category": "Printing & Stationery", "Tax Type": "Out of Scope", "Paid Through": "Petty Cash",
            "Project": "Client Alpha", "Expense Kind": "Services", "Vendor Name": "Xerox Shop", "Remark": ""
        },
        
        # Valid GST rows (11-13)
        {
            "Sl.No": 11, "Expense Date": "2026-08-04", "Amount": 2500, "Description": "Software License",
            "GST/Non GST": "GST", "Category": "Software Subscriptions", "Tax Type": "GST 18%", "Paid Through": "Bank Account",
            "Project": "Internal IT", "Expense Kind": "Goods", "Vendor Name": "Vendor ABC", "Remark": ""
        },
        {
            "Sl.No": 12, "Expense Date": "2026-08-05", "Amount": 890.15, "Description": "Toner Cartridges",
            "GST/Non GST": "GST", "Category": "Printing & Stationery", "Tax Type": "GST 18%", "Paid Through": "Credit Card",
            "Project": "Internal Office", "Expense Kind": "Goods", "Vendor Name": "Office Depot", "Remark": ""
        },
        {
            "Sl.No": 13, "Expense Date": "2026-08-05", "Amount": 300, "Description": "Internet bills",
            "GST/Non GST": "GST", "Category": "Telephone", "Tax Type": "GST 18%", "Paid Through": "Credit Card",
            "Project": "Internal Office", "Expense Kind": "Services", "Vendor Name": "Airtel", "Remark": ""
        },

        # Valid NON-GST rows (14-15)
        {
            "Sl.No": 14, "Expense Date": "2026-08-06", "Amount": 1000, "Description": "Toll plaza charges",
            "GST/Non GST": "NON_GST", "Category": "Travel", "Tax Type": "Out of Scope", "Paid Through": "Petty Cash",
            "Project": "Client Beta", "Expense Kind": "Services", "Vendor Name": "NHAI Toll", "Remark": ""
        },
        {
            "Sl.No": 15, "Expense Date": "2026-08-06", "Amount": 70, "Description": "Local transport bus",
            "GST/Non GST": "NON GST", "Category": "Travel", "Tax Type": "Out of Scope", "Paid Through": "Petty Cash",
            "Project": "Client Beta", "Expense Kind": "Services", "Vendor Name": "City Bus Transport", "Remark": ""
        },

        # Invalid rows (16-19)
        # Row 16: Invalid GST value
        {
            "Sl.No": 16, "Expense Date": "2026-08-07", "Amount": 120, "Description": "Invalid GST cell test",
            "GST/Non GST": "ABC", "Category": "Travel", "Tax Type": "Out of Scope", "Paid Through": "Petty Cash",
            "Project": "Client Beta", "Expense Kind": "Services", "Vendor Name": "City Bus Transport", "Remark": ""
        },
        # Row 17: Missing Amount
        {
            "Sl.No": 17, "Expense Date": "2026-08-07", "Amount": "", "Description": "Missing amount cell test",
            "GST/Non GST": "NON-GST", "Category": "Travel", "Tax Type": "Out of Scope", "Paid Through": "Petty Cash",
            "Project": "Client Beta", "Expense Kind": "Services", "Vendor Name": "City Bus", "Remark": ""
        },
        # Row 18: Missing Vendor Name
        {
            "Sl.No": 18, "Expense Date": "2026-08-08", "Amount": 550, "Description": "Missing vendor cell test",
            "GST/Non GST": "GST", "Category": "Hardware", "Tax Type": "GST 18%", "Paid Through": "Credit Card",
            "Project": "Client Beta", "Expense Kind": "Goods", "Vendor Name": "", "Remark": ""
        },
        # Row 19: Negative Amount & Invalid Date
        {
            "Sl.No": 19, "Expense Date": "invalid-date-value", "Amount": -100, "Description": "Bad amount and date test",
            "GST/Non GST": "NON-GST", "Category": "Hardware", "Tax Type": "Out of Scope", "Paid Through": "Credit Card",
            "Project": "Client Beta", "Expense Kind": "Goods", "Vendor Name": "Local Shop", "Remark": ""
        }
    ]

    df = pd.DataFrame(data)
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    df.to_excel(output_path, index=False, engine="openpyxl")
    print(f"Sample Excel sheet generated successfully at: {output_path}")

if __name__ == "__main__":
    target = os.path.abspath(os.path.join(os.path.dirname(__file__), "Sample dataset.xlsx"))
    create_sample_excel(target)
