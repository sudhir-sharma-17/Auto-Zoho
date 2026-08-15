import { 
  UploadSession, 
  UploadSessionDetail, 
  ExcelValidationResponse,
  ZohoStatus,
  ZohoReport,
  ZohoReportDetails
} from '../types';

const API_BASE = 'http://localhost:8000/api';

export const api = {
  getHealth: async (): Promise<{ status: string; message: string }> => {
    const res = await fetch(`${API_BASE}/health`);
    if (!res.ok) throw new Error('API server unreachable');
    return res.json();
  },

  validateExcel: async (file: File): Promise<ExcelValidationResponse> => {
    const formData = new FormData();
    formData.append('file', file);

    const res = await fetch(`${API_BASE}/excel/validate`, {
      method: 'POST',
      body: formData,
    });

    if (!res.ok) {
      let errorDetail: any = 'Validation request failed';
      try {
        const errorData = await res.json();
        errorDetail = errorData.detail || errorData.message || errorDetail;
      } catch (e) {
        // Fallback
      }
      throw new Error(
        typeof errorDetail === 'object' 
          ? JSON.stringify(errorDetail) 
          : errorDetail
      );
    }

    return res.json();
  },

  getHistory: async (): Promise<UploadSession[]> => {
    const res = await fetch(`${API_BASE}/uploads/history`);
    if (!res.ok) throw new Error('Failed to fetch upload history');
    return res.json();
  },

  getSessionDetails: async (
    sessionId: number,
    filters?: { status?: string; gst?: string; search?: string }
  ): Promise<UploadSessionDetail> => {
    const params = new URLSearchParams();
    if (filters?.status) params.append('status', filters.status);
    if (filters?.gst) params.append('gst', filters.gst);
    if (filters?.search) params.append('search', filters.search);

    const res = await fetch(`${API_BASE}/uploads/${sessionId}?${params.toString()}`);
    if (!res.ok) throw new Error('Failed to fetch session details');
    return res.json();
  },

  getErrorDownloadUrl: (sessionId: number): string => {
    return `${API_BASE}/uploads/${sessionId}/errors`;
  },

  deleteSession: async (sessionId: number): Promise<{ status: string; message: string }> => {
    const res = await fetch(`${API_BASE}/uploads/${sessionId}`, {
      method: 'DELETE',
    });
    if (!res.ok) throw new Error('Failed to delete validation session.');
    return res.json();
  },

  clearHistory: async (): Promise<{ status: string; message: string }> => {
    const res = await fetch(`${API_BASE}/uploads/history`, {
      method: 'DELETE',
    });
    if (!res.ok) throw new Error('Failed to clear validation history.');
    return res.json();
  },

  getZohoStatus: async (): Promise<ZohoStatus> => {
    const res = await fetch(`${API_BASE}/zoho/status`);
    if (!res.ok) throw new Error('Failed to fetch Zoho connection status.');
    return res.json();
  },

  disconnectZoho: async (): Promise<{ message: string }> => {
    const res = await fetch(`${API_BASE}/zoho/disconnect`, {
      method: 'POST',
    });
    if (!res.ok) throw new Error('Failed to disconnect Zoho integration.');
    return res.json();
  },

  testZohoConnection: async (): Promise<{ status: string; message: string }> => {
    const res = await fetch(`${API_BASE}/zoho/test`);
    if (!res.ok) {
      let errDetail = 'Connection check failed';
      try {
        const d = await res.json();
        errDetail = d.detail || errDetail;
      } catch (e) {}
      throw new Error(errDetail);
    }
    return res.json();
  },

  getZohoReports: async (): Promise<ZohoReport[]> => {
    const res = await fetch(`${API_BASE}/zoho/reports`);
    if (!res.ok) {
      let errDetail = 'Failed to load Zoho reports list';
      try {
        const d = await res.json();
        errDetail = d.detail || errDetail;
      } catch (e) {}
      throw new Error(errDetail);
    }
    return res.json();
  },

  getZohoReportDetails: async (reportId: string): Promise<ZohoReportDetails> => {
    const res = await fetch(`${API_BASE}/zoho/reports/${reportId}`);
    if (!res.ok) {
      let errDetail = 'Failed to load report details';
      try {
        const d = await res.json();
        errDetail = d.detail || errDetail;
      } catch (e) {}
      throw new Error(errDetail);
    }
    return res.json();
  },

  getZohoConnectUrl: (): string => {
    return `${API_BASE}/zoho/connect`;
  },

  checkZohoScopes: async (): Promise<{ connected: boolean; has_create_scope: boolean }> => {
    const res = await fetch(`${API_BASE}/zoho/check-scopes`);
    if (!res.ok) throw new Error('Failed to check Zoho authorization scopes.');
    return res.json();
  },

  createTestExpense: async (
    recordId: number,
    gstReportId: string,
    nongstReportId: string,
    categoryId?: string | null,
    projectId?: string | null,
    vendorName?: string | null,
    taxId?: string | null,
    paidThroughId?: string | null,
    expenseKindId?: string | null,
    gstNonGstId?: string | null
  ): Promise<any> => {
    const res = await fetch(`${API_BASE}/zoho/expenses/test-create`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        record_id: recordId,
        gst_report_id: gstReportId,
        nongst_report_id: nongstReportId,
        category_id: categoryId,
        project_id: projectId,
        vendor_name: vendorName,
        tax_id: taxId,
        paid_through_id: paidThroughId,
        expense_kind_id: expenseKindId,
        gst_non_gst_id: gstNonGstId,
      }),
    });
    if (!res.ok) {
      let errDetail = 'Failed to create test expense';
      try {
        const d = await res.json();
        errDetail = d.detail || errDetail;
      } catch (e) {}
      throw new Error(errDetail);
    }
    return res.json();
  },

  getZohoMasterCategories: async (): Promise<any[]> => {
    const res = await fetch(`${API_BASE}/zoho/master-data/categories`);
    if (!res.ok) throw new Error('Failed to load Zoho master categories');
    return res.json();
  },

  getZohoMasterProjects: async (): Promise<any[]> => {
    const res = await fetch(`${API_BASE}/zoho/master-data/projects`);
    if (!res.ok) throw new Error('Failed to load Zoho master projects');
    return res.json();
  },

  getZohoMasterVendors: async (): Promise<any[]> => {
    const res = await fetch(`${API_BASE}/zoho/master-data/vendors`);
    if (!res.ok) throw new Error('Failed to load Zoho master vendors');
    return res.json();
  },

  getZohoMasterTaxes: async (): Promise<any[]> => {
    const res = await fetch(`${API_BASE}/zoho/master-data/taxes`);
    if (!res.ok) throw new Error('Failed to load Zoho master taxes');
    return res.json();
  },

  getZohoMasterPaymentModes: async (): Promise<any[]> => {
    const res = await fetch(`${API_BASE}/zoho/master-data/payment-modes`);
    if (!res.ok) throw new Error('Failed to load Zoho master payment modes');
    return res.json();
  },

  getZohoMasterExpenseKinds: async (): Promise<any[]> => {
    const res = await fetch(`${API_BASE}/zoho/master-data/expense-kinds`);
    if (!res.ok) throw new Error('Failed to load Zoho master expense kinds');
    return res.json();
  },

  getZohoMasterGstOptions: async (): Promise<any[]> => {
    const res = await fetch(`${API_BASE}/zoho/master-data/gst-options`);
    if (!res.ok) throw new Error('Failed to load Zoho master GST options');
    return res.json();
  },

  triggerBulkCreate: async (
    sessionId: number,
    gstReportId: string,
    nongstReportId: string,
    skipInvalid: boolean,
    limit?: number | null,
    categoryMappings?: Record<string, string>,
    projectMappings?: Record<string, string>,
    taxMappings?: Record<string, string>,
    paidThroughMappings?: Record<string, string>,
    expenseKindMappings?: Record<string, string>,
    gstNonGstMappings?: Record<string, string>
  ): Promise<any> => {
    const res = await fetch(`${API_BASE}/zoho/expenses/bulk-create`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        session_id: sessionId,
        gst_report_id: gstReportId,
        nongst_report_id: nongstReportId,
        skip_invalid: skipInvalid,
        limit: limit,
        category_mappings: categoryMappings,
        project_mappings: projectMappings,
        tax_mappings: taxMappings,
        paid_through_mappings: paidThroughMappings,
        expense_kind_mappings: expenseKindMappings,
        gst_non_gst_mappings: gstNonGstMappings,
      }),
    });
    if (!res.ok) {
      let errDetail = 'Failed to start bulk creation';
      try {
        const d = await res.json();
        errDetail = d.detail || errDetail;
      } catch (e) {}
      throw new Error(errDetail);
    }
    return res.json();
  },

  getBulkStatus: async (sessionId: number): Promise<any> => {
    const res = await fetch(`${API_BASE}/zoho/expenses/bulk-status?session_id=${sessionId}`);
    if (!res.ok) throw new Error('Failed to fetch bulk creation status');
    return res.json();
  },

  getErrorReportDownloadUrl: (sessionId: number): string => {
    return `${API_BASE}/zoho/sessions/${sessionId}/error-report`;
  },

  triggerDryRun: async (
    sessionId: number,
    gstReportId: string,
    nongstReportId: string
  ): Promise<any> => {
    const res = await fetch(`${API_BASE}/zoho/expenses/dry-run`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        session_id: sessionId,
        gst_report_id: gstReportId,
        nongst_report_id: nongstReportId,
      }),
    });
    if (!res.ok) {
      let errDetail = 'Failed to validate reports for dry run';
      try {
        const d = await res.json();
        errDetail = d.detail || errDetail;
      } catch (e) {}
      throw new Error(errDetail);
    }
    return res.json();
  },

  getLockStatus: async (): Promise<{ has_pin: boolean }> => {
    const res = await fetch(`${API_BASE}/lock/status`);
    if (!res.ok) throw new Error('Failed to fetch PIN lock status.');
    return res.json();
  },

  setupPin: async (pin: string): Promise<any> => {
    const res = await fetch(`${API_BASE}/lock/setup`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ pin }),
    });
    if (!res.ok) {
      let errDetail = 'Failed to setup PIN lock';
      try {
        const d = await res.json();
        errDetail = d.detail || errDetail;
      } catch (e) {}
      throw new Error(errDetail);
    }
    return res.json();
  },

  verifyPin: async (pin: string): Promise<{ verified: boolean }> => {
    const res = await fetch(`${API_BASE}/lock/verify`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ pin }),
    });
    if (!res.ok) {
      let errDetail = 'Incorrect PIN passcode';
      try {
        const d = await res.json();
        errDetail = d.detail || errDetail;
      } catch (e) {}
      throw new Error(errDetail);
    }
    return res.json();
  },

  disablePin: async (pin: string): Promise<any> => {
    const res = await fetch(`${API_BASE}/lock/disable`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ pin }),
    });
    if (!res.ok) {
      let errDetail = 'Failed to disable PIN passcode';
      try {
        const d = await res.json();
        errDetail = d.detail || errDetail;
      } catch (e) {}
      throw new Error(errDetail);
    }
    return res.json();
  }
};
