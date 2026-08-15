import pandas as pd
import numpy as np
from typing import List, Dict, Any

def parse_excel_file(file_path: str) -> List[Dict[str, Any]]:
    """
    Parses an Excel spreadsheet using pandas.
    Preserves all rows (including duplicates and empty rows) and maps Excel row indices (1-indexed, starting at 2).
    """
    # Read the excel workbook using openpyxl engine
    df = pd.read_excel(file_path, sheet_name=0, dtype=object)
    
    # Standardize columns (strip whitespace, but preserve names)
    df.columns = [str(col).strip() for col in df.columns]
    
    # We want to replace all NaN values with None
    df = df.replace({np.nan: None, pd.NA: None, pd.NaT: None})
    
    records = []
    for idx, row in df.iterrows():
        # Excel data row numbers are 1-indexed, with headers being row 1
        excel_row_num = idx + 2
        
        row_dict = row.to_dict()
        row_dict['_row_number'] = excel_row_num
        records.append(row_dict)
        
    return records
