export interface ExpenseRecord {
  id: number;
  session_id: number;
  original_row_number: number;
  expense_date: string | null;
  amount: number | null;
  description: string | null;
  gst_type: 'GST' | 'NON_GST' | 'UNKNOWN' | null;
  category: string | null;
  tax_type: string | null;
  paid_through: string | null;
  project: string | null;
  expense_kind: string | null;
  vendor_name: string | null;
  status: 'VALID' | 'INVALID';
  errors: string | null;
  zoho_status?: string | null;
  zoho_expense_id?: string | null;
  zoho_error?: string | null;
}

export interface UploadSession {
  id: number;
  file_name: string;
  timestamp: string;
  total_rows: number;
  valid_rows: number;
  invalid_rows: number;
  gst_count: number;
  nongst_count: number;
  status: 'Validated' | 'Errors' | 'Failed';
  error_report_path: string | null;
}

export interface UploadSessionDetail extends UploadSession {
  records: ExpenseRecord[];
}

export interface ExcelValidationResponse {
  session: UploadSession;
  records: ExpenseRecord[];
  message: string;
}

export interface ValidationErrorResponse {
  message: string;
  missing_columns?: string[];
}

export interface ZohoStatus {
  connected: boolean;
  organization: string | null;
}

export interface ZohoReport {
  report_id: string;
  report_name: string;
  status: string;
  total: number;
  start_date?: string;
  end_date?: string;
}

export interface ZohoReportDetails {
  report_id: string;
  report_name: string;
  status: string;
  total: number;
  start_date: string;
  end_date: string;
  description?: string;
}
