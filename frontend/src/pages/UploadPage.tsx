import React, { useState, useRef, DragEvent, useEffect } from 'react';
import { 
  Upload as UploadIcon,
  FileSpreadsheet, 
  Trash2, 
  Play, 
  CheckCircle, 
  AlertCircle, 
  AlertTriangle,
  Download, 
  RefreshCw, 
  Search,
  ArrowRight,
  HelpCircle,
  Clock,
  Layers,
  Sparkles,
  Database,
  X
} from 'lucide-react';
import { api } from '../services/api';
import { ExcelValidationResponse, ExpenseRecord, ZohoReport } from '../types';

interface UploadPageProps {
  onNavigateToTab: (tab: string) => void;
}

export const UploadPage: React.FC<UploadPageProps> = ({ onNavigateToTab }) => {
  const [activeStep, setActiveStep] = useState<number>(1);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [isDragActive, setIsDragActive] = useState<boolean>(false);
  const [isLoading, setIsLoading] = useState<boolean>(false);

  // Zoho Integration States (Phase 2 & 3A)
  const [connected, setConnected] = useState<boolean>(false);
  const [hasCreateScope, setHasCreateScope] = useState<boolean>(true);
  const [reportsList, setReportsList] = useState<ZohoReport[]>([]);
  const [loadingReports, setLoadingReports] = useState<boolean>(false);
  const [reportsError, setReportsError] = useState<string | null>(null);
  const [gstReportId, setGstReportId] = useState<string>('');
  const [nongstReportId, setNongstReportId] = useState<string>('');
  const [bypassSameReportWarning, setBypassSameReportWarning] = useState<boolean>(false);

  // Master data states
  const [masterCategories, setMasterCategories] = useState<any[]>([]);
  const [masterProjects, setMasterProjects] = useState<any[]>([]);
  const [masterVendors, setMasterVendors] = useState<any[]>([]);
  const [masterTaxes, setMasterTaxes] = useState<any[]>([]);
  const [masterPaymentModes, setMasterPaymentModes] = useState<any[]>([]);
  const [masterExpenseKinds, setMasterExpenseKinds] = useState<any[]>([]);
  const [masterGstOptions, setMasterGstOptions] = useState<any[]>([]);
  const [loadingMasterData, setLoadingMasterData] = useState<boolean>(false);
  const [masterDataError, setMasterDataError] = useState<string | null>(null);

  // Field mappings states (Excel value -> Mapped Zoho object)
  const [mappedCategories, setMappedCategories] = useState<Record<string, any>>({});
  const [mappedProjects, setMappedProjects] = useState<Record<string, any>>({});
  const [mappedVendors, setMappedVendors] = useState<Record<string, any>>({});
  const [mappedTaxes, setMappedTaxes] = useState<Record<string, any>>({});
  const [mappedPaymentModes, setMappedPaymentModes] = useState<Record<string, any>>({});
  const [mappedExpenseKinds, setMappedExpenseKinds] = useState<Record<string, any>>({});
  const [mappedGstOptions, setMappedGstOptions] = useState<Record<string, any>>({});

  // Controlled bulk creation states (Phase 3B)
  const [skipInvalid, setSkipInvalid] = useState<boolean>(false);
  const [limitCount, setLimitCount] = useState<number | null>(null);
  const [bulkStatus, setBulkStatus] = useState<string>('IDLE');
  const [bulkIsRunning, setBulkIsRunning] = useState<boolean>(false);
  const [bulkTotalRows, setBulkTotalRows] = useState<number>(0);
  const [bulkProcessedCount, setBulkProcessedCount] = useState<number>(0);
  const [bulkCreatedCount, setBulkCreatedCount] = useState<number>(0);
  const [bulkFailedCount, setBulkFailedCount] = useState<number>(0);
  const [bulkCurrentRow, setBulkCurrentRow] = useState<number | null>(null);
  const [bulkCurrentStatus, setBulkCurrentStatus] = useState<string>('IDLE');
  const [bulkRecords, setBulkRecords] = useState<any[]>([]);
  const [bulkError, setBulkError] = useState<string | null>(null);
  const [showResultsDrawer, setShowResultsDrawer] = useState<boolean>(false);
  const [showResumeDialog, setShowResumeDialog] = useState<boolean>(false);
  const [resumeCounts, setResumeCounts] = useState<{ created: number; pending: number; failed: number } | null>(null);

  // Single test expense creation states (Phase 3A)
  const [selectedRecordForTest, setSelectedRecordForTest] = useState<ExpenseRecord | null>(null);
  const [showConfirmCreate, setShowConfirmCreate] = useState<boolean>(false);
  const [isCreatingTest, setIsCreatingTest] = useState<boolean>(false);
  const [creationResult, setCreationResult] = useState<{
    status: 'success' | 'error';
    expense_id?: string;
    field?: string;
    message?: string;
  } | null>(null);

  const loadMasterData = async () => {
    setLoadingMasterData(true);
    setMasterDataError(null);
    try {
      const status = await api.getZohoStatus();
      setConnected(status.connected);
      if (status.connected) {
        const scopeRes = await api.checkZohoScopes();
        setHasCreateScope(scopeRes.has_create_scope);
        if (scopeRes.has_create_scope) {
          const [cats, projs, vends, txs, pmodes, kinds, gstOpts] = await Promise.all([
            api.getZohoMasterCategories(),
            api.getZohoMasterProjects(),
            api.getZohoMasterVendors(),
            api.getZohoMasterTaxes(),
            api.getZohoMasterPaymentModes(),
            api.getZohoMasterExpenseKinds(),
            api.getZohoMasterGstOptions()
          ]);
          setMasterCategories(cats);
          setMasterProjects(projs);
          setMasterVendors(vends);
          setMasterTaxes(txs);
          setMasterPaymentModes(pmodes);
          setMasterExpenseKinds(kinds);
          setMasterGstOptions(gstOpts);
        }
      }
    } catch (err: any) {
      setMasterDataError(err.message || 'Failed to query Zoho status or master-data.');
    } finally {
      setLoadingMasterData(false);
    }
  };

  const checkConnectionAndLoadReports = async () => {
    setLoadingReports(true);
    setReportsError(null);
    try {
      const status = await api.getZohoStatus();
      setConnected(status.connected);
      if (status.connected) {
        const scopeRes = await api.checkZohoScopes();
        setHasCreateScope(scopeRes.has_create_scope);
        if (scopeRes.has_create_scope) {
          const reports = await api.getZohoReports();
          setReportsList(reports);
        }
      }
    } catch (err: any) {
      setReportsError(err.message || 'Failed to query Zoho status or reports.');
    } finally {
      setLoadingReports(false);
    }
  };

  useEffect(() => {
    if (activeStep === 3) {
      loadMasterData();
    } else if (activeStep === 4) {
      checkConnectionAndLoadReports();
    }
  }, [activeStep]);

  // API Response States
  const [validationData, setValidationData] = useState<ExcelValidationResponse | null>(null);
  const [structuralError, setStructuralError] = useState<{ message: string; missing_columns?: string[] } | null>(null);
  
  // Table filters
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [statusFilter, setStatusFilter] = useState<'ALL' | 'VALID' | 'INVALID'>('ALL');
  const [gstFilter, setGstFilter] = useState<'ALL' | 'GST' | 'NON_GST'>('ALL');

  const normalizeString = (s: string): string => {
    if (!s) return "";
    return s.normalize("NFC").replace(/\s+/g, " ").trim().toLowerCase();
  };

  const runAutoMatching = (
    records: ExpenseRecord[],
    cats: any[],
    projs: any[],
    vends: any[],
    txs: any[],
    pmodes: any[],
    kinds: any[],
    gstOpts: any[]
  ) => {
    const uniqueCats = Array.from(new Set(records.map(r => r.category).filter(Boolean))) as string[];
    const uniqueProjs = Array.from(new Set(records.map(r => r.project).filter(Boolean))) as string[];
    const uniqueVends = Array.from(new Set(records.map(r => r.vendor_name).filter(Boolean))) as string[];
    const uniqueTxs = Array.from(new Set(records.map(r => r.tax_type).filter(Boolean))) as string[];
    const uniquePmodes = Array.from(new Set(records.map(r => r.paid_through).filter(Boolean))) as string[];
    const uniqueKinds = Array.from(new Set(records.map(r => r.expense_kind).filter(Boolean))) as string[];
    const uniqueGst = Array.from(new Set(records.map(r => r.gst_type).filter(Boolean))) as string[];

    const newCatMap: Record<string, any> = { ...mappedCategories };
    const newProjMap: Record<string, any> = { ...mappedProjects };
    const newVendMap: Record<string, any> = { ...mappedVendors };
    const newTaxMap: Record<string, any> = { ...mappedTaxes };
    const newPmodeMap: Record<string, any> = { ...mappedPaymentModes };
    const newKindMap: Record<string, any> = { ...mappedExpenseKinds };
    const newGstMap: Record<string, any> = { ...mappedGstOptions };

    // Categories
    uniqueCats.forEach(val => {
      if (newCatMap[val] && newCatMap[val].status !== "unmatched" && newCatMap[val].status !== "multiple") return;
      const target = normalizeString(val);
      const matches = cats.filter(c => normalizeString(c.name) === target);
      if (matches.length === 1) {
        newCatMap[val] = matches[0];
      } else if (matches.length > 1) {
        newCatMap[val] = { status: "multiple", choices: matches };
      } else {
        newCatMap[val] = { status: "unmatched" };
      }
    });

    // Projects
    uniqueProjs.forEach(val => {
      if (newProjMap[val] && newProjMap[val].status !== "unmatched" && newProjMap[val].status !== "multiple") return;
      const target = normalizeString(val);
      const matches = projs.filter(p => normalizeString(p.name) === target);
      if (matches.length === 1) {
        newProjMap[val] = matches[0];
      } else if (matches.length > 1) {
        newProjMap[val] = { status: "multiple", choices: matches };
      } else {
        newProjMap[val] = { status: "unmatched" };
      }
    });

    // Vendors
    uniqueVends.forEach(val => {
      if (newVendMap[val] && newVendMap[val].status !== "unmatched" && newVendMap[val].status !== "multiple") return;
      const target = normalizeString(val);
      const matches = vends.filter(v => normalizeString(v.name) === target);
      if (matches.length === 1) {
        newVendMap[val] = matches[0];
      } else if (matches.length > 1) {
        newVendMap[val] = { status: "multiple", choices: matches };
      } else {
        newVendMap[val] = { status: "unmatched" };
      }
    });

    // Taxes
    uniqueTxs.forEach(val => {
      if (newTaxMap[val] && newTaxMap[val].status !== "unmatched" && newTaxMap[val].status !== "multiple") return;
      const target = normalizeString(val);
      const matches = txs.filter(t => normalizeString(t.name) === target);
      if (matches.length === 1) {
        newTaxMap[val] = matches[0];
      } else if (matches.length > 1) {
        newTaxMap[val] = { status: "multiple", choices: matches };
      } else {
        newTaxMap[val] = { status: "unmatched" };
      }
    });

    // Payment modes (Paid Through)
    uniquePmodes.forEach(val => {
      if (newPmodeMap[val] && newPmodeMap[val].status !== "unmatched" && newPmodeMap[val].status !== "multiple") return;
      const target = normalizeString(val);
      
      const cleanTargetName = (name: string) => {
        return name.replace(/^\d+\.\s*/, "");
      };
      
      const matches = pmodes.filter(m => {
        const nameNorm = normalizeString(m.name);
        const nameCleanNorm = normalizeString(cleanTargetName(m.name));
        return nameNorm === target || nameCleanNorm === target;
      });

      if (matches.length === 1) {
        newPmodeMap[val] = matches[0];
      } else if (matches.length > 1) {
        newPmodeMap[val] = { status: "multiple", choices: matches };
      } else {
        const mapping: Record<string, string> = {
          "cash": "cash",
          "personal card": "personal_card",
          "company card": "corporate_card",
          "corporate card": "corporate_card",
          "cheque": "check",
          "check": "check",
          "bank account": "bank_account",
          "bank transfer": "bank_account"
        };
        const cleaned = val.trim().toLowerCase();
        if (mapping[cleaned]) {
          const id = mapping[cleaned];
          const found = pmodes.find(m => m.id === id);
          newPmodeMap[val] = found || { id, name: val };
        } else {
          newPmodeMap[val] = { status: "unmatched" };
        }
      }
    });

    // Expense Kinds
    uniqueKinds.forEach(val => {
      if (newKindMap[val] && newKindMap[val].status !== "unmatched" && newKindMap[val].status !== "multiple") return;
      const target = normalizeString(val);
      const matches = kinds.filter(k => normalizeString(k.name) === target);
      if (matches.length === 1) {
        newKindMap[val] = matches[0];
      } else if (matches.length > 1) {
        newKindMap[val] = { status: "multiple", choices: matches };
      } else {
        newKindMap[val] = { status: "unmatched" };
      }
    });

    // GST/Non-GST Options
    uniqueGst.forEach(val => {
      if (newGstMap[val] && newGstMap[val].status !== "unmatched" && newGstMap[val].status !== "multiple") return;
      // Match val ('GST' or 'NON_GST') to master data options (name "GST" or "Non-GST")
      const target = normalizeString(val === "GST" ? "GST" : "Non-GST");
      const matches = gstOpts.filter(g => normalizeString(g.name) === target);
      if (matches.length === 1) {
        newGstMap[val] = matches[0];
      } else if (matches.length > 1) {
        newGstMap[val] = { status: "multiple", choices: matches };
      } else {
        newGstMap[val] = { status: "unmatched" };
      }
    });

    setMappedCategories(newCatMap);
    setMappedProjects(newProjMap);
    setMappedVendors(newVendMap);
    setMappedTaxes(newTaxMap);
    setMappedPaymentModes(newPmodeMap);
    setMappedExpenseKinds(newKindMap);
    setMappedGstOptions(newGstMap);
  };

  useEffect(() => {
    if (validationData && activeStep === 3 && masterCategories.length > 0) {
      runAutoMatching(
        validationData.records,
        masterCategories,
        masterProjects,
        masterVendors,
        masterTaxes,
        masterPaymentModes,
        masterExpenseKinds,
        masterGstOptions
      );
    }
  }, [validationData, activeStep, masterCategories, masterProjects, masterVendors, masterTaxes, masterPaymentModes, masterExpenseKinds, masterGstOptions]);

  // Polling loop for bulk creation status (Phase 3B)
  useEffect(() => {
    let timer: any = null;
    
    const checkStatus = async () => {
      if (!validationData) return;
      try {
        const res = await api.getBulkStatus(validationData.session.id);
        setBulkStatus(res.status);
        setBulkIsRunning(res.is_running);
        setBulkTotalRows(res.total_rows);
        setBulkProcessedCount(res.processed_count);
        setBulkCreatedCount(res.created_count);
        setBulkFailedCount(res.failed_count);
        setBulkCurrentRow(res.current_row);
        setBulkCurrentStatus(res.current_status);
        setBulkRecords(res.records || []);
        
        if (!res.is_running) {
          if (activeStep === 7) {
            setActiveStep(8);
          }
          if (timer) clearInterval(timer);
        }
      } catch (err: any) {
        setBulkError(err.message || 'Failed to fetch status update.');
      }
    };

    if (bulkIsRunning && validationData) {
      checkStatus(); // Initial call
      timer = setInterval(checkStatus, 1500);
    }
    
    return () => {
      if (timer) clearInterval(timer);
    };
  }, [bulkIsRunning, validationData, activeStep]);

  // Check for interrupted bulk uploads to prompt resume (Safety Control)
  useEffect(() => {
    if (validationData && validationData.records) {
      const records = validationData.records;
      const created = records.filter(r => r.zoho_status === 'CREATED').length;
      const pending = records.filter(r => r.zoho_status === 'PENDING').length;
      const failed = records.filter(r => r.zoho_status === 'FAILED').length;
      
      if (created > 0 && (pending > 0 || failed > 0)) {
        setResumeCounts({ created, pending, failed });
        setShowResumeDialog(true);
      }
    }
  }, [validationData]);

  // Restore running state on startup or tab load
  useEffect(() => {
    const restoreRunningState = async () => {
      if (validationData && activeStep < 6) {
        try {
          const res = await api.getBulkStatus(validationData.session.id);
          if (res.is_running) {
            setBulkIsRunning(true);
            setBulkStatus(res.status);
            setBulkTotalRows(res.total_rows);
            setBulkProcessedCount(res.processed_count);
            setBulkCreatedCount(res.created_count);
            setBulkFailedCount(res.failed_count);
            setBulkCurrentRow(res.current_row);
            setBulkCurrentStatus(res.current_status);
            setBulkRecords(res.records || []);
            setActiveStep(7);
          }
        } catch (e) {}
      }
    };
    restoreRunningState();
  }, [validationData, activeStep]);

  const allMappingsResolved = (): boolean => {
    if (!validationData) return false;
    const uniqueCats = Array.from(new Set(validationData.records.map(r => r.category).filter(Boolean))) as string[];
    const uniqueProjs = Array.from(new Set(validationData.records.map(r => r.project).filter(Boolean))) as string[];
    const uniqueTxs = Array.from(new Set(validationData.records.map(r => r.tax_type).filter(Boolean))) as string[];
    const uniquePmodes = Array.from(new Set(validationData.records.map(r => r.paid_through).filter(Boolean))) as string[];
    const uniqueKinds = Array.from(new Set(validationData.records.map(r => r.expense_kind).filter(Boolean))) as string[];
    const uniqueGst = Array.from(new Set(validationData.records.map(r => r.gst_type).filter(Boolean))) as string[];

    const isCatResolved = uniqueCats.every(k => mappedCategories[k] && mappedCategories[k].status !== "unmatched" && mappedCategories[k].status !== "multiple");
    const isProjResolved = uniqueProjs.every(k => mappedProjects[k] && mappedProjects[k].status !== "unmatched" && mappedProjects[k].status !== "multiple");
    const isTaxResolved = uniqueTxs.every(k => mappedTaxes[k] && mappedTaxes[k].status !== "unmatched" && mappedTaxes[k].status !== "multiple");
    const isPmodeResolved = uniquePmodes.every(k => mappedPaymentModes[k] && mappedPaymentModes[k].status !== "unmatched" && mappedPaymentModes[k].status !== "multiple");
    const isKindResolved = uniqueKinds.every(k => mappedExpenseKinds[k] && mappedExpenseKinds[k].status !== "unmatched" && mappedExpenseKinds[k].status !== "multiple");
    const isGstResolved = uniqueGst.every(k => mappedGstOptions[k] && mappedGstOptions[k].status !== "unmatched" && mappedGstOptions[k].status !== "multiple");

    return isCatResolved && isProjResolved && isTaxResolved && isPmodeResolved && isKindResolved && isGstResolved;
  };

  const handleInitiateTestCreate = (record: ExpenseRecord) => {
    setSelectedRecordForTest(record);
    setCreationResult(null);
    setShowConfirmCreate(true);
    setIsCreatingTest(false);
  };

  const handleExecuteTestCreate = async () => {
    if (!selectedRecordForTest) return;
    setIsCreatingTest(true);
    setCreationResult(null);

    const mappedCat = selectedRecordForTest.category ? mappedCategories[selectedRecordForTest.category]?.id : null;
    const mappedProj = selectedRecordForTest.project ? mappedProjects[selectedRecordForTest.project]?.id : null;
    const mappedVend = selectedRecordForTest.vendor_name ? mappedVendors[selectedRecordForTest.vendor_name]?.id : null;
    const mappedTax = selectedRecordForTest.tax_type ? mappedTaxes[selectedRecordForTest.tax_type]?.id : null;
    const mappedPmode = selectedRecordForTest.paid_through ? mappedPaymentModes[selectedRecordForTest.paid_through]?.id : null;
    const mappedKind = selectedRecordForTest.expense_kind ? mappedExpenseKinds[selectedRecordForTest.expense_kind]?.id : null;
    const mappedGst = selectedRecordForTest.gst_type ? mappedGstOptions[selectedRecordForTest.gst_type]?.id : null;

    try {
      const res = await api.createTestExpense(
        selectedRecordForTest.id,
        gstReportId,
        nongstReportId,
        mappedCat,
        mappedProj,
        mappedVend,
        mappedTax,
        mappedPmode,
        mappedKind,
        mappedGst
      );
      if (res.status === 'success') {
        setCreationResult({
          status: 'success',
          expense_id: res.expense_id
        });
      } else {
        setCreationResult({
          status: 'error',
          field: res.field,
          message: res.message
        });
      }
    } catch (err: any) {
      setCreationResult({
        status: 'error',
        field: 'Network/Server',
        message: err.message || 'An unexpected error occurred during posting.'
      });
    } finally {
      setIsCreatingTest(false);
    }
  };

  const [dryRunData, setDryRunData] = useState<any | null>(null);
  const [executingDryRun, setExecutingDryRun] = useState<boolean>(false);
  const [dryRunError, setDryRunError] = useState<string | null>(null);

  const handleExecuteDryRun = async () => {
    if (!validationData) return;
    setExecutingDryRun(true);
    setDryRunError(null);
    setDryRunData(null);
    try {
      const res = await api.triggerDryRun(
        validationData.session.id,
        gstReportId,
        nongstReportId
      );
      setDryRunData(res);
    } catch (err: any) {
      setDryRunError(err.message || 'Failed to complete dry run checks.');
    } finally {
      setExecutingDryRun(false);
    }
  };

  const handleExecuteBulkCreate = async () => {
    if (!validationData) return;
    setBulkError(null);
    setBulkIsRunning(true);
    
    // Compile mappings to pass to backend
    const categoryMappings: Record<string, string> = {};
    Object.entries(mappedCategories).forEach(([k, v]) => { if (v && v.id) categoryMappings[k] = v.id; });
    
    const projectMappings: Record<string, string> = {};
    Object.entries(mappedProjects).forEach(([k, v]) => { if (v && v.id) projectMappings[k] = v.id; });
    
    const taxMappings: Record<string, string> = {};
    Object.entries(mappedTaxes).forEach(([k, v]) => { if (v && v.id) taxMappings[k] = v.id; });
    
    const paidThroughMappings: Record<string, string> = {};
    Object.entries(mappedPaymentModes).forEach(([k, v]) => { if (v && v.id) paidThroughMappings[k] = v.id; });
    
    const expenseKindMappings: Record<string, string> = {};
    Object.entries(mappedExpenseKinds).forEach(([k, v]) => { if (v && v.id) expenseKindMappings[k] = v.id; });
    
    const gstNonGstMappings: Record<string, string> = {};
    Object.entries(mappedGstOptions).forEach(([k, v]) => { if (v && v.id) gstNonGstMappings[k] = v.id; });

    try {
      await api.triggerBulkCreate(
        validationData.session.id,
        gstReportId,
        nongstReportId,
        skipInvalid,
        limitCount,
        categoryMappings,
        projectMappings,
        taxMappings,
        paidThroughMappings,
        expenseKindMappings,
        gstNonGstMappings
      );
      setBulkIsRunning(true);
    } catch (err: any) {
      setBulkError(err.message || 'Failed to start bulk creation.');
      setBulkIsRunning(false);
    }
  };


  const fileInputRef = useRef<HTMLInputElement>(null);

  // Stepper Setup (expanded to 8 steps in Phase 4)
  const steps = [
    { num: '01', name: 'Upload', desc: 'Excel import' },
    { num: '02', name: 'Validate', desc: 'Data checks' },
    { num: '03', name: 'Map Fields', desc: 'Align master-data' },
    { num: '04', name: 'Reports', desc: 'Select Zoho' },
    { num: '05', name: 'Preview', desc: 'Dry run review' },
    { num: '06', name: 'Confirm', desc: 'Safety checks' },
    { num: '07', name: 'Create', desc: 'Create expenses' },
    { num: '08', name: 'Results', desc: 'View summary' }
  ];

  // Drag and drop handlers
  const handleDrag = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === "dragenter" || e.type === "dragover") {
      setIsDragActive(true);
    } else if (e.type === "dragleave") {
      setIsDragActive(false);
    }
  };

  const handleDrop = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragActive(false);

    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      validateAndSetFile(e.dataTransfer.files[0]);
    }
  };

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      validateAndSetFile(e.target.files[0]);
    }
  };

  const validateAndSetFile = (file: File) => {
    setStructuralError(null);
    const suffix = file.name.split('.').pop()?.toLowerCase();
    if (suffix !== 'xlsx' && suffix !== 'xls') {
      setStructuralError({
        message: 'Unsupported file format. Please upload an Excel spreadsheet (.xlsx, .xls).'
      });
      setSelectedFile(null);
      return;
    }
    setSelectedFile(file);
  };

  const removeFile = () => {
    setSelectedFile(null);
    setStructuralError(null);
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  const triggerFileBrowser = () => {
    fileInputRef.current?.click();
  };

  // Submit to API
  const handleValidateFile = async () => {
    if (!selectedFile) return;
    setIsLoading(true);
    setStructuralError(null);

    try {
      const data = await api.validateExcel(selectedFile);
      setValidationData(data);
      setActiveStep(2);
    } catch (err: any) {
      // Parse structured JSON validation error from server if exists
      try {
        const parsedObj = JSON.parse(err.message);
        setStructuralError({
          message: parsedObj.message || 'Excel Validation Failed',
          missing_columns: parsedObj.missing_columns
        });
      } catch (e) {
        setStructuralError({
          message: err.message || 'Failed to upload and validate spreadsheet.'
        });
      }
    } finally {
      setIsLoading(false);
    }
  };

  const handleReset = () => {
    setSelectedFile(null);
    setValidationData(null);
    setStructuralError(null);
    setSearchQuery('');
    setStatusFilter('ALL');
    setGstFilter('ALL');
    setActiveStep(1);
  };

  // Error Report Download Trigger
  const handleDownloadErrors = () => {
    if (!validationData) return;
    const url = api.getErrorDownloadUrl(validationData.session.id);
    window.open(url, '_blank');
  };

  // Table filters & Search logic
  const filteredRecords = validationData ? validationData.records.filter((rec) => {
    // Status Filter
    if (statusFilter === 'VALID' && rec.status !== 'VALID') return false;
    if (statusFilter === 'INVALID' && rec.status !== 'INVALID') return false;

    // GST Filter
    if (gstFilter === 'GST' && rec.gst_type !== 'GST') return false;
    if (gstFilter === 'NON_GST' && rec.gst_type !== 'NON_GST') return false;

    // Text Search
    if (searchQuery.trim() !== '') {
      const query = searchQuery.toLowerCase();
      const desc = (rec.description || '').toLowerCase();
      const cat = (rec.category || '').toLowerCase();
      const vendor = (rec.vendor_name || '').toLowerCase();
      const project = (rec.project || '').toLowerCase();

      return desc.includes(query) || cat.includes(query) || vendor.includes(query) || project.includes(query);
    }

    return true;
  }) : [];

  const renderMappingSection = (
    title: string, 
    excelKeys: string[], 
    mappingState: Record<string, any>, 
    setMappingState: React.Dispatch<React.SetStateAction<Record<string, any>>>, 
    masterOptions: any[]
  ) => {
    if (excelKeys.length === 0) return null;
    
    return (
      <div className="space-y-4">
        <h5 className="font-bold text-slate-800 text-xs uppercase tracking-wider">{title}</h5>
        <div className="bg-white rounded-xl border border-slate-200 shadow-xs overflow-hidden">
          <table className="w-full text-left border-collapse text-xs">
            <thead>
              <tr className="bg-slate-50 border-b border-slate-200 text-slate-500 font-semibold">
                <th className="px-4 py-2.5 w-1/3">Excel Value</th>
                <th className="px-4 py-2.5 w-1/2">Zoho Match</th>
                <th className="px-4 py-2.5 text-center">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {excelKeys.map(key => {
                const mappedVal = mappingState[key];
                const isUnmatched = !mappedVal || mappedVal.status === "unmatched";
                const isMultiple = mappedVal && mappedVal.status === "multiple";
                const isMatched = mappedVal && !isUnmatched && !isMultiple;
                
                return (
                  <tr key={key} className="hover:bg-slate-50/50">
                    <td className="px-4 py-3 font-semibold text-slate-750">{key}</td>
                    <td className="px-4 py-3">
                      {isMatched && (
                        <div className="font-medium text-slate-900 flex items-center gap-1.5">
                          <span>{mappedVal.name}</span>
                          {mappedVal.parent_name && (
                            <span className="text-[10px] text-slate-400 font-normal">
                              (Parent: {mappedVal.parent_name})
                            </span>
                          )}
                        </div>
                      )}
                      
                      {isMultiple && (
                        <div className="space-y-1.5">
                          <span className="text-[10px] text-rose-500 font-bold block">
                            Multiple Zoho options match this value.
                          </span>
                          <select
                            onChange={(e) => {
                              const option = mappedVal.choices.find((c: any) => c.id === e.target.value);
                              if (option) {
                                setMappingState(prev => ({ ...prev, [key]: option }));
                              }
                            }}
                            className="bg-white border border-rose-300 text-xs font-semibold rounded-lg px-2.5 py-1 text-slate-800"
                            defaultValue=""
                          >
                            <option value="" disabled>Select Option...</option>
                            {mappedVal.choices.map((c: any) => (
                              <option key={c.id} value={c.id}>
                                {c.name} {c.parent_name ? `(Parent: ${c.parent_name})` : ""}
                              </option>
                            ))}
                          </select>
                        </div>
                      )}
                      
                      {isUnmatched && (
                        <select
                          onChange={(e) => {
                            const option = masterOptions.find(o => o.id === e.target.value);
                            if (option) {
                              setMappingState(prev => ({ ...prev, [key]: option }));
                            }
                          }}
                          className="bg-white border border-amber-300 text-xs font-semibold rounded-lg px-2.5 py-1 text-slate-850"
                          defaultValue=""
                        >
                          <option value="" disabled>Select Zoho Option...</option>
                          {masterOptions.map(o => (
                            <option key={o.id} value={o.id}>
                              {o.name} {o.parent_name ? `(Parent: ${o.parent_name})` : ""}
                            </option>
                          ))}
                        </select>
                      )}
                    </td>
                    <td className="px-4 py-3 text-center">
                      {isMatched && <span className="text-emerald-600 font-bold text-sm">✓</span>}
                      {(isUnmatched || isMultiple) && <span className="text-amber-500 font-bold text-sm">⚠</span>}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    );
  };

  return (
    <div className="space-y-8">
      {/* Page Header */}
      <div>
        <h3 className="text-xl font-semibold text-slate-900 dark:text-slate-100">Upload Expenses</h3>
        <p className="text-xs text-slate-500 dark:text-slate-400">Import your Excel expense file and validate columns and rows before creating entries.</p>
      </div>

      {/* Progress Stepper */}
      <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-xs dark:bg-slate-900 dark:border-slate-800">
        <div className="grid grid-cols-8 gap-2">
          {steps.map((s, idx) => {
            const stepNum = idx + 1;
            const isCompleted = activeStep > stepNum;
            const isActive = activeStep === stepNum;
            return (
              <div key={s.num} className="flex flex-col gap-2 relative">
                {/* Visual Line connector */}
                {stepNum < 8 && (
                  <div className={`hidden md:block absolute top-4 left-[60%] right-[-40%] h-0.5 z-0 ${
                    activeStep > stepNum ? 'bg-indigo-600 dark:bg-indigo-500' : 'bg-slate-200 dark:bg-slate-800'
                  }`} />
                )}
                
                {/* Step circle */}
                <div className="flex items-center gap-2.5 z-10">
                  <div className={`h-8 w-8 rounded-full flex items-center justify-center text-xs font-semibold border transition-all duration-300 ${
                    isCompleted 
                      ? 'bg-indigo-600 text-white border-indigo-600 dark:bg-indigo-500 dark:border-indigo-500' 
                      : isActive 
                        ? 'bg-white text-indigo-600 border-indigo-600 ring-4 ring-indigo-50 dark:ring-indigo-950/50 font-bold dark:bg-slate-900 dark:text-indigo-400 dark:border-indigo-400' 
                        : 'bg-slate-50 text-slate-400 border-slate-200 dark:bg-slate-800 dark:text-slate-500 dark:border-slate-700'
                  }`}>
                    {isCompleted ? <CheckCircle className="h-4.5 w-4.5" /> : s.num}
                  </div>
                  <div className="hidden md:block">
                    <p className={`text-xs font-semibold ${isActive ? 'text-indigo-600 dark:text-indigo-400' : 'text-slate-700 dark:text-slate-350'}`}>
                      {s.name}
                    </p>
                    <p className="text-[10px] text-slate-400 font-normal dark:text-slate-500">{s.desc}</p>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* STEP 1: UPLOAD EXCEL */}
      {activeStep === 1 && (
        <div className="space-y-6">
          {/* Drag & Drop Container */}
          <div 
            onDragEnter={handleDrag}
            onDragOver={handleDrag}
            onDragLeave={handleDrag}
            onDrop={handleDrop}
            className={`border-2 border-dashed rounded-xl p-12 text-center transition-all duration-200 flex flex-col items-center justify-center min-h-[300px] ${
              isDragActive 
                ? 'border-indigo-500 bg-indigo-50/30 dark:bg-indigo-950/20' 
                : 'border-slate-300 bg-white hover:border-indigo-400 hover:bg-slate-50/50 dark:border-slate-850 dark:bg-slate-900 dark:hover:bg-slate-800/50'
            }`}
          >
            <input 
              type="file" 
              ref={fileInputRef}
              onChange={handleFileSelect}
              accept=".xlsx,.xls"
              className="hidden"
            />
            
            <div className="p-4 bg-indigo-50 text-indigo-600 rounded-full mb-4 dark:bg-indigo-950/60 dark:text-indigo-400">
              <UploadIcon className="h-8 w-8" />
            </div>
            
            <p className="text-base font-semibold text-slate-900 mb-1 dark:text-slate-100">Upload your Excel file</p>
            <p className="text-sm text-slate-500 mb-6 dark:text-slate-400">Drag and drop your file here, or click to browse</p>
            
            <button
              onClick={triggerFileBrowser}
              className="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-sm font-medium shadow-xs hover:shadow-md transition-all duration-200 cursor-pointer"
            >
              Browse Files
            </button>
            
            <p className="text-xs text-slate-400 mt-4 dark:text-slate-500">Supported formats: .xlsx, .xls</p>
          </div>

          {/* Structural validation failed error banner */}
          {structuralError && (
            <div className="bg-rose-50 border border-rose-200 rounded-xl p-6 text-left space-y-3 dark:bg-rose-950/40 dark:border-rose-900/50">
              <div className="flex items-start gap-3 text-rose-800 dark:text-rose-400">
                <AlertCircle className="h-5.5 w-5.5 shrink-0 mt-0.5" />
                <div>
                  <h4 className="font-semibold text-sm">Excel Validation Failed</h4>
                  <p className="text-xs text-rose-700 mt-1 dark:text-rose-450">{structuralError.message}</p>
                </div>
              </div>

              {structuralError.missing_columns && (
                <div className="pl-8.5 space-y-2">
                  <p className="text-xs font-semibold text-rose-800 dark:text-rose-400">Missing columns:</p>
                  <ul className="list-disc list-inside text-xs text-rose-700 space-y-1 dark:text-rose-450">
                    {structuralError.missing_columns.map(col => (
                      <li key={col}>{col}</li>
                    ))}
                  </ul>
                  <p className="text-xs font-medium text-rose-800 mt-3 pt-1 border-t border-rose-100 dark:text-rose-400 dark:border-rose-900/40">
                    Please correct the Excel file structure and upload it again.
                  </p>
                </div>
              )}
            </div>
          )}

          {/* Selected File State */}
          {selectedFile && !structuralError && (
            <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-xs flex items-center justify-between dark:bg-slate-900 dark:border-slate-800">
              <div className="flex items-center gap-4">
                <div className="p-3 bg-indigo-50 text-indigo-600 rounded-lg dark:bg-indigo-950/50 dark:text-indigo-400">
                  <FileSpreadsheet className="h-6 w-6" />
                </div>
                <div>
                  <h4 className="font-medium text-slate-900 dark:text-slate-100">{selectedFile.name}</h4>
                  <p className="text-xs text-slate-500 font-normal mt-0.5 dark:text-slate-450">
                    Size: {(selectedFile.size / 1024).toFixed(1)} KB • Excel Spreadsheet
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-3">
                <button
                  onClick={removeFile}
                  disabled={isLoading}
                  className="inline-flex items-center gap-1.5 px-3 py-2 border border-slate-200 hover:bg-slate-50 text-slate-600 hover:text-slate-900 rounded-lg text-xs font-medium transition-colors cursor-pointer dark:border-slate-850 dark:hover:bg-slate-800 dark:text-slate-400 dark:hover:text-slate-100"
                >
                  <Trash2 className="h-4 w-4" />
                  Remove
                </button>
                <button
                  onClick={handleValidateFile}
                  disabled={isLoading}
                  className="inline-flex items-center gap-1.5 px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-xs font-medium shadow-xs hover:shadow-md transition-all duration-200 cursor-pointer disabled:opacity-60"
                >
                  {isLoading ? (
                    <>
                      <RefreshCw className="h-4 w-4 animate-spin" />
                      Validating...
                    </>
                  ) : (
                    <>
                      <Play className="h-4 w-4 fill-current" />
                      Validate File
                    </>
                  )}
                </button>
              </div>
            </div>
          )}
        </div>
      )}

      {/* STEP 2: VALIDATE ROW-LEVEL DATA */}
      {activeStep === 2 && validationData && (
        <div className="space-y-6">
          {/* File summary details panel */}
          <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-xs dark:bg-slate-900 dark:border-slate-800">
            <div className="flex items-center justify-between pb-4 border-b border-slate-100 dark:border-slate-800">
              <div>
                <h4 className="font-semibold text-slate-950 dark:text-slate-100">File Validation Summary</h4>
                <p className="text-xs text-slate-500 mt-0.5 dark:text-slate-450">{validationData.session.file_name}</p>
              </div>
              <div className="flex gap-3">
                {validationData.session.invalid_rows > 0 ? (
                  <>
                    <button
                      onClick={handleDownloadErrors}
                      className="inline-flex items-center gap-1.5 px-3.5 py-2 bg-rose-50 text-rose-700 border border-rose-200 hover:bg-rose-100 rounded-lg text-xs font-semibold transition-colors cursor-pointer dark:bg-rose-950/40 dark:text-rose-400 dark:border-rose-900/50 dark:hover:bg-rose-900/50"
                    >
                      <Download className="h-4 w-4" />
                      Download Error Report
                    </button>
                    <button
                      onClick={handleReset}
                      className="inline-flex items-center gap-1.5 px-3.5 py-2 border border-slate-200 hover:bg-slate-50 text-slate-700 rounded-lg text-xs font-medium transition-colors cursor-pointer dark:border-slate-800 dark:hover:bg-slate-850 dark:text-slate-300"
                    >
                      <RefreshCw className="h-4 w-4" />
                      Upload Corrected File
                    </button>
                  </>
                ) : (
                  <button
                    onClick={() => setActiveStep(3)}
                    className="inline-flex items-center gap-1.5 px-5 py-2.5 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-xs font-semibold shadow-xs hover:shadow-md transition-all duration-200 cursor-pointer"
                  >
                    Continue
                    <ArrowRight className="h-4.5 w-4.5" />
                  </button>
                )}
              </div>
            </div>

            {/* Metrics values grid */}
            <div className="grid grid-cols-2 md:grid-cols-5 gap-6 pt-6">
              <div>
                <p className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider dark:text-slate-500">Total Rows</p>
                <h5 className="text-xl font-bold text-slate-800 mt-1 dark:text-slate-200">{validationData.session.total_rows}</h5>
              </div>
              <div>
                <p className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider dark:text-slate-500">GST Count</p>
                <h5 className="text-xl font-bold text-indigo-600 mt-1 dark:text-indigo-400">{validationData.session.gst_count}</h5>
              </div>
              <div>
                <p className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider dark:text-slate-500">Non-GST Count</p>
                <h5 className="text-xl font-bold text-indigo-600 mt-1 dark:text-indigo-400">{validationData.session.nongst_count}</h5>
              </div>
              <div>
                <p className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider dark:text-slate-500">Valid Rows</p>
                <h5 className="text-xl font-bold text-emerald-600 mt-1 dark:text-emerald-450">{validationData.session.valid_rows}</h5>
              </div>
              <div>
                <p className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider dark:text-slate-500">Errors</p>
                <h5 className={`text-xl font-bold mt-1 ${validationData.session.invalid_rows > 0 ? 'text-rose-600 animate-pulse dark:text-rose-400' : 'text-slate-500'}`}>
                  {validationData.session.invalid_rows}
                </h5>
              </div>
            </div>
            
            {validationData.session.invalid_rows > 0 && (
              <div className="mt-6 p-4 bg-rose-50/50 border border-rose-100 rounded-lg flex items-start gap-3 dark:bg-rose-950/20 dark:border-rose-900/40">
                <AlertCircle className="h-5 w-5 text-rose-500 shrink-0 mt-0.5" />
                <p className="text-xs text-rose-700 font-medium dark:text-rose-450">
                  This spreadsheet contains <strong>{validationData.session.invalid_rows} invalid rows</strong>. 
                  You must fix these errors in your source spreadsheet, or download the Error Report to isolate them, 
                  then upload the corrected file. The "Continue" button is locked.
                </p>
              </div>
            )}
          </div>

          {/* Filtering and search row */}
          <div className="flex flex-col md:flex-row gap-4 items-center justify-between">
            {/* Filter Tabs */}
            <div className="flex border border-slate-200 bg-white rounded-lg p-1 gap-1 w-full md:w-auto dark:border-slate-800 dark:bg-slate-900">
              <button
                onClick={() => setStatusFilter('ALL')}
                className={`px-3 py-1.5 rounded-md text-xs font-semibold transition-colors cursor-pointer ${
                  statusFilter === 'ALL' ? 'bg-indigo-50 text-indigo-700 dark:bg-indigo-950/60 dark:text-indigo-400' : 'text-slate-600 hover:bg-slate-50 dark:text-slate-400 dark:hover:bg-slate-800'
                }`}
              >
                All Rows ({validationData.session.total_rows})
              </button>
              <button
                onClick={() => setStatusFilter('VALID')}
                className={`px-3 py-1.5 rounded-md text-xs font-semibold transition-colors cursor-pointer ${
                  statusFilter === 'VALID' ? 'bg-emerald-50 text-emerald-700 dark:bg-emerald-950/60 dark:text-emerald-400' : 'text-slate-600 hover:bg-slate-50 dark:text-slate-400 dark:hover:bg-slate-800'
                }`}
              >
                Valid ({validationData.session.valid_rows})
              </button>
              <button
                onClick={() => setStatusFilter('INVALID')}
                className={`px-3 py-1.5 rounded-md text-xs font-semibold transition-colors cursor-pointer ${
                  statusFilter === 'INVALID' ? 'bg-rose-50 text-rose-700 dark:bg-rose-950/60 dark:text-rose-455' : 'text-slate-600 hover:bg-slate-50 dark:text-slate-400 dark:hover:bg-slate-800'
                }`}
              >
                Errors ({validationData.session.invalid_rows})
              </button>
            </div>

            <div className="flex gap-3 w-full md:w-auto items-center">
              {/* GST Filter Selector */}
              <select
                value={gstFilter}
                onChange={(e) => setGstFilter(e.target.value as any)}
                className="bg-white border border-slate-200 text-xs font-medium rounded-lg px-3 py-2 text-slate-700 focus:outline-hidden focus:ring-2 focus:ring-indigo-500 dark:bg-slate-800 dark:border-slate-700 dark:text-slate-200"
              >
                <option value="ALL">All GST Types</option>
                <option value="GST">GST Only</option>
                <option value="NON_GST">Non-GST Only</option>
              </select>

              {/* Search Field */}
              <div className="relative w-full md:w-64">
                <Search className="absolute left-3 top-2.5 h-4 w-4 text-slate-400 dark:text-slate-500" />
                <input
                  type="text"
                  placeholder="Search description, category, vendor..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="w-full bg-white border border-slate-200 rounded-lg pl-9 pr-4 py-2 text-xs text-slate-800 placeholder-slate-400 focus:outline-hidden focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 dark:bg-slate-800 dark:border-slate-700 dark:text-slate-200 dark:placeholder-slate-500"
                />
              </div>
            </div>
          </div>

          {/* Preview Table */}
          <div className="bg-white rounded-xl border border-slate-200 shadow-xs overflow-hidden dark:bg-slate-900 dark:border-slate-800">
            <div className="overflow-x-auto max-h-[400px]">
              <table className="w-full text-left border-collapse text-xs">
                <thead>
                  <tr className="bg-slate-50 border-b border-slate-200 text-slate-500 font-medium sticky top-0 z-20 dark:bg-slate-900/60 dark:border-slate-800 dark:text-slate-400">
                    <th className="px-4 py-3 w-16">Row</th>
                    <th className="px-4 py-3 w-28">Date</th>
                    <th className="px-4 py-3 w-24">Amount</th>
                    <th className="px-4 py-3">Description</th>
                    <th className="px-4 py-3 w-24">GST Type</th>
                    <th className="px-4 py-3">Category</th>
                    <th className="px-4 py-3">Paid Through</th>
                    <th className="px-4 py-3">Project</th>
                    <th className="px-4 py-3">Vendor</th>
                    <th className="px-4 py-3 w-20 text-center">Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                  {filteredRecords.length > 0 ? (
                    filteredRecords.map((rec) => {
                      const hasErrors = rec.status === 'INVALID';
                      return (
                        <React.Fragment key={rec.id}>
                          <tr className={`transition-colors duration-150 ${hasErrors ? 'bg-rose-50/30 dark:bg-rose-950/20' : 'hover:bg-slate-50/50 dark:hover:bg-slate-800/50'}`}>
                            <td className="px-4 py-3.5 font-semibold text-slate-400 dark:text-slate-550">{rec.original_row_number}</td>
                            <td className="px-4 py-3.5 font-medium text-slate-700 dark:text-slate-300">{rec.expense_date || 'N/A'}</td>
                            <td className="px-4 py-3.5 font-bold text-slate-900 dark:text-slate-100">
                              {rec.amount !== null ? `₹${rec.amount.toFixed(2)}` : 'N/A'}
                            </td>
                            <td className="px-4 py-3.5 text-slate-700 font-medium dark:text-slate-300">{rec.description || 'N/A'}</td>
                            <td className="px-4 py-3.5 font-semibold">
                              <span className={`px-2 py-0.5 rounded-sm text-[10px] ${
                                rec.gst_type === 'GST' 
                                  ? 'bg-indigo-50 text-indigo-700 border border-indigo-100 dark:bg-indigo-950/50 dark:text-indigo-400 dark:border-indigo-900/50' 
                                  : rec.gst_type === 'NON_GST' 
                                    ? 'bg-slate-100 text-slate-700 border border-slate-200 dark:bg-slate-800 dark:text-slate-300 dark:border-slate-700' 
                                    : 'bg-rose-50 text-rose-700 border border-rose-100 dark:bg-rose-950/50 dark:text-rose-450 dark:border-rose-900/50'
                              }`}>
                                {rec.gst_type || 'UNKNOWN'}
                              </span>
                            </td>
                            <td className="px-4 py-3.5 text-slate-600 dark:text-slate-400">{rec.category || 'N/A'}</td>
                            <td className="px-4 py-3.5 text-slate-600 dark:text-slate-400">{rec.paid_through || 'N/A'}</td>
                            <td className="px-4 py-3.5 text-slate-600 dark:text-slate-400">{rec.project || 'N/A'}</td>
                            <td className="px-4 py-3.5 text-slate-600 font-medium dark:text-slate-350">{rec.vendor_name || 'N/A'}</td>
                            <td className="px-4 py-3.5 text-center">
                              <div className="flex justify-center">
                                {hasErrors ? (
                                  <span title={rec.errors || ''}>
                                    <AlertCircle className="h-4.5 w-4.5 text-rose-500" />
                                  </span>
                                ) : (
                                  <CheckCircle className="h-4.5 w-4.5 text-emerald-500" />
                                )}
                              </div>
                            </td>
                          </tr>
                          {/* Inner error logs rendering beneath the row */}
                          {hasErrors && rec.errors && (
                            <tr className="bg-rose-50/20 dark:bg-rose-950/10">
                              <td colSpan={10} className="px-4 py-2 border-t border-rose-50 text-left dark:border-rose-950/30">
                                <div className="pl-6 flex items-start gap-1.5 text-rose-700 font-medium text-[11px] dark:text-rose-400">
                                  <span className="font-bold text-rose-800 dark:text-rose-350">Errors:</span>
                                  <span>{rec.errors.split(';').join(', ')}</span>
                                </div>
                              </td>
                            </tr>
                          )}
                        </React.Fragment>
                      );
                    })
                  ) : (
                    <tr>
                      <td colSpan={10} className="px-6 py-12 text-center text-slate-400 font-medium dark:text-slate-500">
                        No rows match your active filter / search parameters.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}
      {/* STEP 3: MAP ZOHO FIELDS */}
      {activeStep === 3 && (
        <div className="bg-white rounded-xl border border-slate-200 shadow-xs p-8 space-y-6 animate-fade-in dark:bg-slate-900 dark:border-slate-800">
          <div className="flex items-center justify-between pb-4 border-b border-slate-100 dark:border-slate-800">
            <div>
              <h4 className="font-semibold text-slate-950 dark:text-slate-100">Map Zoho Fields</h4>
              <p className="text-xs text-slate-500 mt-0.5 dark:text-slate-400">Align Excel spreadsheet values with Zoho Expense master-data dropdown options.</p>
            </div>
            <button 
              onClick={loadMasterData} 
              disabled={loadingMasterData}
              className="px-3 py-1.5 border border-slate-200 bg-white hover:bg-slate-50 text-slate-700 rounded-lg text-xs font-semibold cursor-pointer inline-flex items-center gap-1.5 dark:border-slate-800 dark:bg-slate-800 dark:hover:bg-slate-700 dark:text-slate-350"
            >
              <RefreshCw className={`h-3.5 w-3.5 ${loadingMasterData ? 'animate-spin' : ''}`} />
              Sync Master Data
            </button>
          </div>

          {loadingMasterData ? (
            <div className="py-12 flex items-center justify-center gap-2 text-xs text-slate-500 font-medium dark:text-slate-400">
              <RefreshCw className="h-4 w-4 animate-spin text-indigo-500" />
              Retrieving master-data lists from Zoho Expense...
            </div>
          ) : !hasCreateScope ? (
            <div className="p-8 border border-dashed border-slate-200 rounded-xl text-center space-y-4 max-w-lg mx-auto bg-white animate-fade-in dark:border-slate-800 dark:bg-slate-900">
              <div className="mx-auto h-12 w-12 bg-amber-50 rounded-full flex items-center justify-center text-amber-600 dark:bg-amber-950/40">
                <AlertTriangle className="h-6 w-6" />
              </div>
              <div className="space-y-1">
                <h5 className="text-sm font-bold text-slate-900 dark:text-slate-100">Additional Permission Required</h5>
                <p className="text-xs text-slate-500 leading-relaxed font-normal dark:text-slate-400">
                  Additional Zoho Expense permission is required. Please reconnect your account to enable posting.
                </p>
              </div>
              <button
                onClick={() => onNavigateToTab('settings')}
                className="px-4 py-2 bg-amber-650 hover:bg-amber-750 text-white rounded-lg text-xs font-semibold shadow-xs cursor-pointer inline-flex items-center gap-1.5"
              >
                Reconnect Zoho
                <ArrowRight className="h-3.5 w-3.5" />
              </button>
            </div>
          ) : !connected ? (
            <div className="p-8 border border-dashed border-slate-200 rounded-xl text-center space-y-4 max-w-lg mx-auto bg-white dark:border-slate-800 dark:bg-slate-900">
              <div className="mx-auto h-12 w-12 bg-amber-50 rounded-full flex items-center justify-center text-amber-600 dark:bg-amber-950/40">
                <AlertCircle className="h-6 w-6" />
              </div>
              <div className="space-y-1">
                <h5 className="text-sm font-bold text-slate-900 dark:text-slate-100">Zoho Connection Required</h5>
                <p className="text-xs text-slate-500 leading-relaxed font-normal dark:text-slate-400">
                  Your Zoho Expense organization must be authorized before mapping fields. 
                  Connect your account in application settings first.
                </p>
              </div>
              <button
                onClick={() => onNavigateToTab('settings')}
                className="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-xs font-semibold shadow-xs cursor-pointer inline-flex items-center gap-1.5"
              >
                Go to Connection Settings
                <ArrowRight className="h-3.5 w-3.5" />
              </button>
            </div>
          ) : masterDataError ? (
            <div className="p-4 bg-rose-50 border border-rose-100 text-rose-800 rounded-lg text-xs font-medium flex items-start gap-2.5 dark:bg-rose-950/40 dark:border-rose-900/50 dark:text-rose-455">
              <AlertCircle className="h-4.5 w-4.5 text-rose-600 shrink-0 mt-0.5" />
              <div>
                <p>Unable to retrieve master-data from Zoho.</p>
                <p className="text-rose-700 mt-1 font-normal dark:text-rose-400">{masterDataError}</p>
                <button 
                  onClick={loadMasterData}
                  className="mt-3 text-indigo-600 hover:text-indigo-800 font-semibold underline dark:text-indigo-400 dark:hover:text-indigo-300"
                >
                  Retry request
                </button>
              </div>
            </div>
          ) : (
            <div className="space-y-8 max-w-3xl mx-auto">
              {validationData && (
                <>
                  {/* Category mappings */}
                  {(() => {
                    const uniqueCats = Array.from(new Set(validationData.records.map(r => r.category).filter(Boolean))) as string[];
                    return renderMappingSection("Category", uniqueCats, mappedCategories, setMappedCategories, masterCategories);
                  })()}

                  {/* Paid through mappings */}
                  {(() => {
                    const uniquePmodes = Array.from(new Set(validationData.records.map(r => r.paid_through).filter(Boolean))) as string[];
                    return renderMappingSection("Paid Through Account / Method", uniquePmodes, mappedPaymentModes, setMappedPaymentModes, masterPaymentModes);
                  })()}

                  {/* Project mappings */}
                  {(() => {
                    const uniqueProjs = Array.from(new Set(validationData.records.map(r => r.project).filter(Boolean))) as string[];
                    return renderMappingSection("Project", uniqueProjs, mappedProjects, setMappedProjects, masterProjects);
                  })()}

                  {/* Tax mappings */}
                  {(() => {
                    const uniqueTxs = Array.from(new Set(validationData.records.map(r => r.tax_type).filter(Boolean))) as string[];
                    return renderMappingSection("Tax Type", uniqueTxs, mappedTaxes, setMappedTaxes, masterTaxes);
                  })()}

                  {/* Expense Kind mappings */}
                  {(() => {
                    const uniqueKinds = Array.from(new Set(validationData.records.map(r => r.expense_kind).filter(Boolean))) as string[];
                    return renderMappingSection("Expense Kind", uniqueKinds, mappedExpenseKinds, setMappedExpenseKinds, masterExpenseKinds);
                  })()}

                  {/* GST/Non-GST mappings */}
                  {(() => {
                    const uniqueGst = Array.from(new Set(validationData.records.map(r => r.gst_type).filter(Boolean))) as string[];
                    return renderMappingSection("GST/Non-GST Type", uniqueGst, mappedGstOptions, setMappedGstOptions, masterGstOptions);
                  })()}
                 </>
              )}

              {/* Action buttons */}
              <div className="flex justify-between pt-4 border-t border-slate-100 dark:border-slate-800">
                <button
                  onClick={handleReset}
                  className="px-4 py-2 border border-slate-200 hover:bg-slate-50 text-slate-700 rounded-lg text-xs font-semibold cursor-pointer dark:border-slate-800 dark:bg-slate-800 dark:hover:bg-slate-700 dark:text-slate-300"
                >
                  Restart Workflow
                </button>
                <button
                  onClick={() => setActiveStep(4)}
                  disabled={!allMappingsResolved()}
                  className="inline-flex items-center gap-1.5 px-5 py-2.5 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-xs font-semibold shadow-xs hover:shadow-md transition-all duration-200 cursor-pointer disabled:opacity-60 disabled:cursor-not-allowed"
                >
                  Continue to Reports Selection
                  <ArrowRight className="h-4.5 w-4.5" />
                </button>
              </div>
            </div>
          )}
        </div>
      )}

      {/* STEP 4: SELECT ZOHO REPORTS */}
      {activeStep === 4 && (
        <div className="bg-white rounded-xl border border-slate-200 shadow-xs p-8 space-y-6 animate-fade-in dark:bg-slate-900 dark:border-slate-800">
          <div className="flex items-center justify-between pb-4 border-b border-slate-100 dark:border-slate-800">
            <div>
              <h4 className="font-semibold text-slate-950 dark:text-slate-100">Select Destination Reports</h4>
              <p className="text-xs text-slate-500 mt-0.5 dark:text-slate-400">Route GST and NON-GST expense rows into their respective Zoho report folders.</p>
            </div>
          </div>

          {loadingReports ? (
            <div className="py-12 flex items-center justify-center gap-2 text-xs text-slate-500 font-medium dark:text-slate-400">
              <RefreshCw className="h-4 w-4 animate-spin text-indigo-500" />
              Fetching reports from Zoho Expense...
            </div>
          ) : reportsError ? (
            <div className="p-4 bg-rose-50 border border-rose-100 text-rose-800 rounded-lg text-xs font-medium flex items-start gap-2.5 dark:bg-rose-950/40 dark:border-rose-900/50 dark:text-rose-455">
              <AlertCircle className="h-4.5 w-4.5 text-rose-600 shrink-0 mt-0.5" />
              <div>
                <p>Unable to retrieve expense reports from Zoho.</p>
                <p className="text-rose-700 mt-1 font-normal dark:text-rose-400">{reportsError}</p>
                <button 
                  onClick={checkConnectionAndLoadReports}
                  className="mt-3 text-indigo-600 hover:text-indigo-800 font-semibold underline dark:text-indigo-400 dark:hover:text-indigo-300"
                >
                  Retry request
                </button>
              </div>
            </div>
          ) : (
            <div className="space-y-6 max-w-xl mx-auto">
              {/* GST dropdown */}
              <div className="space-y-2">
                <label className="block text-xs font-bold text-slate-500 uppercase tracking-wider dark:text-slate-400">
                  GST Expenses Destination Report
                </label>
                <select
                  value={gstReportId}
                  onChange={(e) => {
                    setGstReportId(e.target.value);
                  }}
                  className="w-full bg-white border border-slate-200 text-xs font-semibold rounded-lg px-3 py-2.5 text-slate-800 focus:outline-hidden focus:ring-2 focus:ring-indigo-500 dark:bg-slate-800 dark:border-slate-700 dark:text-slate-205"
                >
                  <option value="">Select GST Report...</option>
                  {reportsList.map(r => (
                    <option key={r.report_id} value={r.report_id}>{r.report_name}</option>
                  ))}
                </select>
                {gstReportId && (
                  <div className="p-3 bg-slate-50 border border-slate-100 rounded-lg text-xs grid grid-cols-2 gap-3 text-slate-655 font-normal dark:bg-slate-900/50 dark:border-slate-800 dark:text-slate-400">
                    <div>
                      <span className="font-bold block text-[10px] text-slate-400 uppercase tracking-wide dark:text-slate-500">Status</span>
                      <span className="font-semibold text-slate-700 capitalize dark:text-slate-300">
                        {reportsList.find(r => r.report_id === gstReportId)?.status || 'N/A'}
                      </span>
                    </div>
                    <div>
                      <span className="font-bold block text-[10px] text-slate-400 uppercase tracking-wide dark:text-slate-500">Period</span>
                      <span className="font-semibold text-slate-700 dark:text-slate-300">
                        {(() => {
                          const r = reportsList.find(r => r.report_id === gstReportId);
                          return r && r.start_date && r.end_date 
                            ? `${r.start_date} ➡️ ${r.end_date}` 
                            : 'N/A';
                        })()}
                      </span>
                    </div>
                  </div>
                )}
              </div>

              {/* NON-GST dropdown */}
              <div className="space-y-2">
                <label className="block text-xs font-bold text-slate-500 uppercase tracking-wider dark:text-slate-400">
                  NON-GST Expenses Destination Report
                </label>
                <select
                  value={nongstReportId}
                  onChange={(e) => {
                    setNongstReportId(e.target.value);
                  }}
                  className="w-full bg-white border border-slate-200 text-xs font-semibold rounded-lg px-3 py-2.5 text-slate-800 focus:outline-hidden focus:ring-2 focus:ring-indigo-500 dark:bg-slate-800 dark:border-slate-700 dark:text-slate-205"
                >
                  <option value="">Select NON-GST Report...</option>
                  {reportsList.map(r => (
                    <option key={r.report_id} value={r.report_id}>{r.report_name}</option>
                  ))}
                </select>
                {nongstReportId && (
                  <div className="p-3 bg-slate-50 border border-slate-100 rounded-lg text-xs grid grid-cols-2 gap-3 text-slate-655 font-normal dark:bg-slate-900/50 dark:border-slate-800 dark:text-slate-400">
                    <div>
                      <span className="font-bold block text-[10px] text-slate-400 uppercase tracking-wide dark:text-slate-500">Status</span>
                      <span className="font-semibold text-slate-700 capitalize dark:text-slate-300">
                        {reportsList.find(r => r.report_id === nongstReportId)?.status || 'N/A'}
                      </span>
                    </div>
                    <div>
                      <span className="font-bold block text-[10px] text-slate-400 uppercase tracking-wide dark:text-slate-500">Period</span>
                      <span className="font-semibold text-slate-700 dark:text-slate-300">
                        {(() => {
                          const r = reportsList.find(r => r.report_id === nongstReportId);
                          return r && r.start_date && r.end_date 
                            ? `${r.start_date} ➡️ ${r.end_date}` 
                            : 'N/A';
                        })()}
                      </span>
                    </div>
                  </div>
                )}
              </div>

              {/* Same report safety warning */}
              {gstReportId && nongstReportId && gstReportId === nongstReportId && !bypassSameReportWarning && (
                <div className="p-4 bg-amber-50 border border-amber-100 rounded-xl space-y-3 dark:bg-amber-950/40 dark:border-amber-900/50">
                  <div className="flex items-start gap-2.5 text-amber-800 dark:text-amber-400">
                    <AlertTriangle className="h-5 w-5 text-amber-600 shrink-0 mt-0.5" />
                    <div>
                      <h5 className="text-xs font-bold uppercase tracking-wider">Same Report Warning</h5>
                      <p className="text-xs text-amber-700 mt-1 leading-relaxed dark:text-amber-450">
                        The same Zoho report has been selected for both GST and NON-GST expenses.
                      </p>
                    </div>
                  </div>
                  <div className="flex gap-2 justify-end pl-7.5">
                    <button
                      onClick={() => setNongstReportId('')}
                      className="px-3 py-1.5 border border-slate-200 bg-white hover:bg-slate-50 text-slate-700 rounded-lg text-xs font-semibold cursor-pointer dark:border-slate-800 dark:bg-slate-850 dark:hover:bg-slate-800 dark:text-slate-300"
                    >
                      Cancel
                    </button>
                    <button
                      onClick={() => setBypassSameReportWarning(true)}
                      className="px-3 py-1.5 bg-amber-600 hover:bg-amber-700 text-white rounded-lg text-xs font-semibold cursor-pointer"
                    >
                      Use Same Report
                    </button>
                  </div>
                </div>
              )}

              {/* Action buttons */}
              <div className="flex justify-between pt-4 border-t border-slate-100 dark:border-slate-800">
                <button
                  onClick={() => setActiveStep(3)}
                  className="px-4 py-2 border border-slate-200 hover:bg-slate-50 text-slate-700 rounded-lg text-xs font-semibold cursor-pointer dark:border-slate-800 dark:bg-slate-850 dark:hover:bg-slate-800 dark:text-slate-300"
                >
                  Back to Mappings
                </button>
                <button
                  onClick={() => setActiveStep(5)}
                  disabled={!gstReportId || !nongstReportId || (gstReportId === nongstReportId && !bypassSameReportWarning)}
                  className="inline-flex items-center gap-1.5 px-5 py-2.5 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-xs font-semibold shadow-xs hover:shadow-md transition-all duration-200 cursor-pointer disabled:opacity-60 disabled:cursor-not-allowed"
                >
                  Continue to Preview
                  <ArrowRight className="h-4.5 w-4.5" />
                </button>
              </div>
            </div>
          )
        }
      </div>
    )}

      {/* STEP 5: INTEGRATION PREVIEW & DRY RUN */}
      {activeStep === 5 && validationData && (
        <div className="space-y-6 animate-fade-in">
          {validationData.session.invalid_rows > 0 && !skipInvalid && (
            <div className="p-5 bg-rose-50 border border-rose-100 rounded-xl space-y-4 max-w-2xl mx-auto text-left shadow-xs dark:bg-rose-950/40 dark:border-rose-900/50">
              <div className="flex items-start gap-3 text-rose-800 dark:text-rose-450">
                <AlertCircle className="h-5 w-5 text-rose-600 shrink-0 mt-0.5" />
                <div>
                  <h5 className="text-xs font-bold uppercase tracking-wider">Spreadsheet Validation Errors</h5>
                  <p className="text-xs text-rose-700 mt-1 leading-relaxed dark:text-rose-400">
                    There are <strong>{validationData.session.invalid_rows} invalid rows</strong> containing errors. You cannot upload these rows to Zoho Expense.
                  </p>
                </div>
              </div>
              <div className="flex gap-3 justify-end pl-8">
                <button
                  onClick={handleReset}
                  className="px-3.5 py-1.5 border border-slate-200 bg-white hover:bg-slate-50 text-slate-700 rounded-lg text-xs font-semibold cursor-pointer dark:border-slate-800 dark:bg-slate-850 dark:hover:bg-slate-800 dark:text-slate-350"
                >
                  Cancel Bulk Upload
                </button>
                <button
                  onClick={() => setSkipInvalid(true)}
                  className="px-3.5 py-1.5 bg-rose-600 hover:bg-rose-750 text-white rounded-lg text-xs font-semibold cursor-pointer"
                >
                  Create Only Valid Rows ({validationData.session.valid_rows})
                </button>
              </div>
            </div>
          )}

          {/* Summary Cards */}
          <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-xs dark:bg-slate-900 dark:border-slate-800">
            <div className="flex items-center justify-between pb-4 border-b border-slate-100 dark:border-slate-800">
              <div>
                <h4 className="font-semibold text-slate-950 dark:text-slate-100">Integration Preview & Routing</h4>
                <p className="text-xs text-slate-500 mt-0.5 dark:text-slate-400">Review targets and execute a dry-run check before posting.</p>
              </div>
              <div className="flex gap-2">
                <button
                  onClick={() => setActiveStep(4)}
                  className="px-4 py-2 border border-slate-200 bg-white hover:bg-slate-50 text-slate-700 rounded-lg text-xs font-semibold cursor-pointer dark:border-slate-800 dark:bg-slate-800 dark:hover:bg-slate-700 dark:text-slate-300"
                >
                  Back to Reports
                </button>
                <button
                  onClick={handleExecuteDryRun}
                  disabled={executingDryRun}
                  className="px-4 py-2 bg-indigo-50 hover:bg-indigo-100 text-indigo-755 border border-indigo-200 rounded-lg text-xs font-semibold cursor-pointer inline-flex items-center gap-1.5 disabled:opacity-60 dark:bg-indigo-950/50 dark:hover:bg-indigo-900/50 dark:text-indigo-400 dark:border-indigo-900/50"
                >
                  <RefreshCw className={`h-3.5 w-3.5 ${executingDryRun ? 'animate-spin' : ''}`} />
                  {executingDryRun ? 'Validating...' : 'Run Dry-Run Check'}
                </button>
                <button
                  onClick={() => {
                    setActiveStep(6);
                  }}
                  disabled={!dryRunData}
                  className="inline-flex items-center gap-1.5 px-5 py-2.5 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-xs font-semibold shadow-xs hover:shadow-md transition-all duration-200 cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  Continue to Confirmation
                  <ArrowRight className="h-4.5 w-4.5" />
                </button>
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-6 pt-6">
              <div className="p-4 bg-slate-50 border border-slate-250/50 rounded-lg dark:bg-slate-900/50 dark:border-slate-800">
                <p className="text-[10px] font-bold text-slate-400 uppercase tracking-wider dark:text-slate-500">Total Valid Rows</p>
                <h5 className="text-xl font-bold text-slate-800 mt-1 dark:text-slate-200">{validationData.session.valid_rows}</h5>
              </div>
              <div className="p-4 bg-indigo-50/40 border border-indigo-100 rounded-lg dark:bg-indigo-950/20 dark:border-indigo-900/40">
                <p className="text-[10px] font-bold text-indigo-500 uppercase tracking-wider dark:text-indigo-455">GST Target Report</p>
                <h5 className="text-xs font-bold text-slate-900 mt-1 truncate dark:text-slate-100" title={reportsList.find(r => r.report_id === gstReportId)?.report_name}>
                  {reportsList.find(r => r.report_id === gstReportId)?.report_name || 'Not Selected'}
                </h5>
                <p className="text-[10px] text-indigo-600 mt-1 font-semibold dark:text-indigo-400">
                  {validationData.records.filter(r => r.status === 'VALID' && r.gst_type === 'GST').length} rows routed
                </p>
              </div>
              <div className="p-4 bg-slate-100 border border-slate-200 rounded-lg dark:bg-slate-800 dark:border-slate-700">
                <p className="text-[10px] font-bold text-slate-550 uppercase tracking-wider dark:text-slate-500">Non-GST Target Report</p>
                <h5 className="text-xs font-bold text-slate-900 mt-1 truncate dark:text-slate-100" title={reportsList.find(r => r.report_id === nongstReportId)?.report_name}>
                  {reportsList.find(r => r.report_id === nongstReportId)?.report_name || 'Not Selected'}
                </h5>
                <p className="text-[10px] text-slate-655 mt-1 font-semibold dark:text-slate-450">
                  {validationData.records.filter(r => r.status === 'VALID' && r.gst_type === 'NON_GST').length} rows routed
                </p>
              </div>
            </div>
          </div>

          {/* Dry Run Outcome Panel */}
          {dryRunError && (
            <div className="p-4 bg-rose-50 border border-rose-100 rounded-xl text-rose-800 text-xs font-semibold flex items-start gap-2.5 dark:bg-rose-950/40 dark:border-rose-900/50 dark:text-rose-455">
              <AlertTriangle className="h-4.5 w-4.5 text-rose-600 shrink-0 mt-0.5" />
              <div>
                <p className="font-bold">Dry-Run Report Validation Failed</p>
                <p className="font-normal text-rose-700 mt-1 dark:text-rose-400">{dryRunError}</p>
              </div>
            </div>
          )}

          {dryRunData && (
            <div className="bg-emerald-50 border border-emerald-100 p-6 rounded-xl space-y-4 dark:bg-emerald-950/20 dark:border-emerald-900/40">
              <div className="flex items-center gap-2.5 text-emerald-800 dark:text-emerald-450">
                <CheckCircle className="h-5 w-5 text-emerald-600" />
                <h4 className="text-xs font-bold uppercase tracking-wider">Dry-Run Verification Succeeded</h4>
              </div>
              
              <div className="grid grid-cols-2 md:grid-cols-4 gap-6 pt-2 text-xs font-semibold text-slate-800 dark:text-slate-205">
                <div>
                  <span className="text-[10px] text-slate-400 font-bold block uppercase dark:text-slate-500">Excel Rows</span>
                  <span className="text-slate-850 font-semibold dark:text-slate-300">{dryRunData.excel_rows}</span>
                </div>
                <div>
                  <span className="text-[10px] text-slate-400 font-bold block uppercase dark:text-slate-500">GST Target Folder</span>
                  <span className="text-slate-850 font-semibold truncate max-w-[150px] block dark:text-slate-300" title={dryRunData.gst_report_name}>
                    {dryRunData.gst_report_name}
                  </span>
                </div>
                <div>
                  <span className="text-[10px] text-slate-400 font-bold block uppercase dark:text-slate-500">Non-GST Target Folder</span>
                  <span className="text-slate-850 font-semibold truncate max-w-[150px] block dark:text-slate-300" title={dryRunData.nongst_report_name}>
                    {dryRunData.nongst_report_name}
                  </span>
                </div>
                <div>
                  <span className="text-[10px] text-slate-400 font-bold block uppercase dark:text-slate-500">WOULD CREATE / CHANGES</span>
                  <span className="text-emerald-700 font-bold dark:text-emerald-400">{dryRunData.would_create} / {dryRunData.changes_made} (Dry Run)</span>
                </div>
              </div>
            </div>
          )}

          {/* Table Preview */}
          <div className="bg-white rounded-xl border border-slate-200 shadow-xs overflow-hidden dark:bg-slate-900 dark:border-slate-800">
            <div className="overflow-x-auto max-h-[400px]">
              <table className="w-full text-left border-collapse text-xs">
                <thead>
                  <tr className="bg-slate-50 border-b border-slate-200 text-slate-500 font-semibold sticky top-0 z-20 dark:bg-slate-900/60 dark:border-slate-800 dark:text-slate-400">
                    <th className="px-4 py-3 w-16">Row</th>
                    <th className="px-4 py-3 w-28">Date</th>
                    <th className="px-4 py-3 w-24">Amount</th>
                    <th className="px-4 py-3">Description</th>
                    <th className="px-4 py-3 w-24">GST Type</th>
                    <th className="px-4 py-3">Category</th>
                    <th className="px-4 py-3">Paid Through</th>
                    <th className="px-4 py-3">Vendor</th>
                    <th className="px-4 py-3 w-36 text-center">Action</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                  {validationData.records
                    .filter(rec => rec.status === 'VALID')
                    .map((rec) => {
                      const matchedCat = rec.category ? mappedCategories[rec.category]?.name : 'N/A';
                      const matchedPmode = rec.paid_through ? mappedPaymentModes[rec.paid_through]?.name : 'N/A';
                      
                      return (
                        <tr key={rec.id} className="hover:bg-slate-50/50 transition-colors dark:hover:bg-slate-800/50">
                          <td className="px-4 py-3.5 font-semibold text-slate-400 dark:text-slate-550">{rec.original_row_number}</td>
                          <td className="px-4 py-3.5 font-medium text-slate-700 dark:text-slate-300">{rec.expense_date || 'N/A'}</td>
                          <td className="px-4 py-3.5 font-bold text-slate-900 dark:text-slate-100">
                            {rec.amount !== null ? `₹${rec.amount.toFixed(2)}` : 'N/A'}
                          </td>
                          <td className="px-4 py-3.5 text-slate-750 font-medium">{rec.description || 'N/A'}</td>
                          <td className="px-4 py-3.5">
                            <span className={`px-2 py-0.5 rounded-sm text-[10px] font-semibold ${
                              rec.gst_type === 'GST' 
                                ? 'bg-indigo-50 text-indigo-700 border border-indigo-100' 
                                : 'bg-slate-100 text-slate-700 border border-slate-200'
                            }`}>
                              {rec.gst_type || 'N/A'}
                            </span>
                          </td>
                          <td className="px-4 py-3.5">
                            <div className="font-semibold text-slate-750">{rec.category || 'N/A'}</div>
                            <div className="text-[10px] text-emerald-600 font-bold">→ Zoho: {matchedCat} ✓</div>
                          </td>
                          <td className="px-4 py-3.5">
                            <div className="font-semibold text-slate-750">{rec.paid_through || 'N/A'}</div>
                            <div className="text-[10px] text-emerald-600 font-bold">→ Zoho: {matchedPmode} ✓</div>
                          </td>
                          <td className="px-4 py-3.5 text-slate-600 font-medium">{rec.vendor_name || 'N/A'}</td>
                          <td className="px-4 py-3.5 text-center">
                            <button
                              onClick={() => handleInitiateTestCreate(rec)}
                              className="px-2.5 py-1.5 bg-indigo-600 hover:bg-indigo-755 text-white rounded-lg text-[10px] font-bold shadow-xs hover:shadow-md transition-all duration-200 cursor-pointer inline-flex items-center gap-1.5"
                            >
                              <Play className="h-3 w-3 shrink-0" />
                              Create Test Expense
                            </button>
                          </td>
                        </tr>
                      );
                    })}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* STEP 6: BULK CREATION SAFETY CONFIRMATION */}
      {activeStep === 6 && validationData && (
        <div className="space-y-6 animate-fade-in text-left">
          <div className="max-w-md mx-auto bg-white rounded-xl border border-slate-200 shadow-xs p-6 space-y-6 dark:bg-slate-900 dark:border-slate-800">
            <h4 className="font-bold text-center text-slate-900 border-b border-slate-100 pb-3 uppercase tracking-wider text-xs dark:text-slate-100 dark:border-slate-800">
              Confirm Bulk Posting
            </h4>
            
            <div className="space-y-3.5 text-xs text-slate-700 font-semibold dark:text-slate-300">
              <div className="flex justify-between">
                <span>Total Excel rows:</span>
                <span className="dark:text-slate-100">{validationData.session.total_rows}</span>
              </div>
              <div className="flex justify-between">
                <span>Valid rows:</span>
                <span className="dark:text-slate-100">{validationData.session.valid_rows}</span>
              </div>
              <div className="flex justify-between">
                <span>Invalid rows:</span>
                <span className="dark:text-slate-100">{validationData.session.invalid_rows}</span>
              </div>
              <div className="flex justify-between border-t border-slate-100 pt-2.5 dark:border-slate-800">
                <span>GST expenses:</span>
                <span className="dark:text-slate-100">{validationData.records.filter(r => r.status === 'VALID' && r.gst_type === 'GST').length}</span>
              </div>
              <div className="flex justify-between">
                <span>NON-GST expenses:</span>
                <span className="dark:text-slate-100">{validationData.records.filter(r => r.status === 'VALID' && r.gst_type === 'NON_GST').length}</span>
              </div>
              <div className="flex justify-between border-t border-slate-100 pt-2.5 dark:border-slate-800">
                <span>Destination GST report:</span>
                <span className="text-slate-950 font-bold truncate max-w-[200px] dark:text-slate-100" title={reportsList.find(r => r.report_id === gstReportId)?.report_name}>
                  {reportsList.find(r => r.report_id === gstReportId)?.report_name || 'Not Selected'}
                </span>
              </div>
              <div className="flex justify-between">
                <span>Destination NON-GST report:</span>
                <span className="text-slate-950 font-bold truncate max-w-[200px] dark:text-slate-100" title={reportsList.find(r => r.report_id === nongstReportId)?.report_name}>
                  {reportsList.find(r => r.report_id === nongstReportId)?.report_name || 'Not Selected'}
                </span>
              </div>
              <div className="flex justify-between border-t border-slate-100 pt-2.5 dark:border-slate-800">
                <span>Reports submitted:</span>
                <span className="text-rose-600 font-bold dark:text-rose-400">NO</span>
              </div>
              <div className="flex justify-between border-t border-slate-100 pt-2.5 text-indigo-900 font-bold dark:text-indigo-400 dark:border-slate-800">
                <span>Expenses to be created:</span>
                <span>{validationData.session.valid_rows}</span>
              </div>
            </div>

            <div className="p-3.5 bg-amber-50 border border-amber-100 rounded-lg text-amber-800 text-xs font-semibold leading-relaxed dark:bg-amber-950/40 dark:border-amber-900/50 dark:text-amber-400">
              ⚠️ <strong>HARD SAFETY BOUNDARY:</strong> This will create REAL expense entries in Zoho Expense. Destination reports will NOT be submitted or approved.
            </div>

            {bulkError && (
              <div className="p-3 bg-rose-50 border border-rose-100 rounded-lg text-rose-700 text-xs font-normal dark:bg-rose-950/40 dark:border-rose-900/50 dark:text-rose-455">
                {bulkError}
              </div>
            )}

            <div className="flex gap-3 justify-end pt-3 border-t border-slate-100 dark:border-slate-800">
              <button
                onClick={() => {
                  setActiveStep(5);
                }}
                className="px-4 py-2 border border-slate-200 bg-white hover:bg-slate-50 text-slate-700 rounded-lg text-xs font-semibold cursor-pointer dark:border-slate-800 dark:bg-slate-850 dark:hover:bg-slate-800 dark:text-slate-300"
              >
                Back to Preview
              </button>
              <button
                onClick={() => {
                  handleExecuteBulkCreate();
                  setActiveStep(7);
                }}
                className="px-5 py-2.5 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-xs font-bold shadow-xs cursor-pointer active:scale-[0.98] transition-transform"
              >
                Create {validationData.session.valid_rows} Expenses
              </button>
            </div>
          </div>
        </div>
      )}

      {/* STEP 7: CREATE EXPENSES PROGRESS */}
      {activeStep === 7 && validationData && (
        <div className="space-y-6 animate-fade-in text-left">
          <div className="max-w-md mx-auto bg-white rounded-xl border border-slate-200 shadow-xs p-6 space-y-6 dark:bg-slate-900 dark:border-slate-800">
            <div className="space-y-1 text-center">
              <h4 className="text-sm font-bold text-slate-900 uppercase tracking-wider dark:text-slate-100">Uploading Batch...</h4>
              <p className="text-xs text-slate-500 font-normal dark:text-slate-400">Creating expenses in Zoho Expense reports.</p>
            </div>
            
            {/* Circular Progress Ring */}
            <div className="relative mx-auto h-28 w-28 flex items-center justify-center mt-2">
              <div className="absolute inset-2.5 rounded-full bg-slate-50/50 border border-slate-100 shadow-inner dark:bg-slate-950/20 dark:border-slate-800"></div>
              
              <svg className="absolute h-full w-full -rotate-90" viewBox="0 0 100 100">
                <circle 
                  cx="50" 
                  cy="50" 
                  r="40" 
                  className="text-slate-100 dark:text-slate-800"
                  stroke="currentColor" 
                  strokeWidth="5" 
                  fill="transparent" 
                />
                <circle 
                  cx="50" 
                  cy="50" 
                  r="40" 
                  className="text-indigo-600 dark:text-indigo-550 transition-all duration-300 ease-out"
                  stroke="currentColor" 
                  strokeWidth="5" 
                  fill="transparent" 
                  strokeDasharray={2 * Math.PI * 40}
                  strokeDashoffset={2 * Math.PI * 40 * (1 - (bulkProcessedCount / (bulkTotalRows || 1)))}
                  strokeLinecap="round"
                />
              </svg>
              
              <div className="flex flex-col items-center z-10">
                <span className="text-xl font-black text-slate-950 tracking-tight dark:text-slate-100">
                  {Math.round((bulkProcessedCount / (bulkTotalRows || 1)) * 100)}%
                </span>
                <span className="text-[9px] font-bold text-slate-400 uppercase tracking-widest mt-0.5 dark:text-slate-500">
                  {bulkProcessedCount}/{bulkTotalRows}
                </span>
              </div>
            </div>

            {/* Created vs Failed Counter */}
            <div className="grid grid-cols-2 gap-3 text-xs font-semibold text-slate-700 p-3 bg-slate-50 border border-slate-150 rounded-xl text-center dark:bg-slate-950/40 dark:border-slate-800 dark:text-slate-300">
              <div>
                <span className="block text-[9px] text-slate-400 uppercase tracking-wider dark:text-slate-500">Created</span>
                <span className="text-emerald-700 font-extrabold text-base dark:text-emerald-450">{bulkCreatedCount}</span>
              </div>
              <div className="border-l border-slate-200 dark:border-slate-800">
                <span className="block text-[9px] text-slate-400 uppercase tracking-wider dark:text-slate-500">Failed</span>
                <span className="text-rose-700 font-extrabold text-base dark:text-rose-400">{bulkFailedCount}</span>
              </div>
            </div>

            {/* Live Activity Feed */}
            <div className="space-y-1.5 text-left">
              <span className="text-[9px] text-slate-400 font-bold uppercase tracking-widest block dark:text-slate-500">Live Upload Logs</span>
              <div className="h-28 overflow-y-auto border border-slate-150 rounded-xl p-3 bg-slate-950 font-mono text-[9px] text-slate-300 space-y-1.5 scrollbar-thin select-none dark:border-slate-800">
                {bulkRecords.length === 0 ? (
                  <div className="text-slate-600 text-center py-9 italic font-medium">Waiting for processing to begin...</div>
                ) : (
                  [...bulkRecords].reverse().map((r) => (
                    <div key={r.id} className="flex items-center justify-between border-b border-slate-900 pb-1 last:border-b-0 last:pb-0 animate-fade-in">
                      <div className="flex items-center gap-1.5 truncate max-w-[70%]">
                        <span className={`h-1 w-1 rounded-full shrink-0 ${
                          r.zoho_status === 'CREATED' ? 'bg-emerald-400' :
                          r.zoho_status === 'FAILED' ? 'bg-rose-500' : 'bg-indigo-400 animate-ping'
                        }`} />
                        <span className="text-slate-500 font-semibold">Row {r.original_row_number}:</span>
                        <span className="text-slate-300 truncate" title={r.description || ''}>{r.description || 'No desc'}</span>
                      </div>
                      <div className="flex items-center gap-2 shrink-0">
                        <span className="font-bold text-slate-100">₹{r.amount !== null ? r.amount.toFixed(2) : '0.00'}</span>
                        <span className={`px-1 rounded-xs font-bold text-[7px] uppercase tracking-wider ${
                          r.zoho_status === 'CREATED' ? 'text-emerald-400' :
                          r.zoho_status === 'FAILED' ? 'text-rose-400' : 'text-indigo-400'
                        }`}>
                          {r.zoho_status || 'POSTING'}
                        </span>
                      </div>
                    </div>
                  ))
                )}
              </div>
            </div>
            
            <div className="p-3 bg-amber-50 border border-amber-100 rounded-xl text-amber-800 text-[10px] font-semibold flex items-center gap-2 dark:bg-amber-950/40 dark:border-amber-900/50 dark:text-amber-400">
              <span className="h-1.5 w-1.5 rounded-full bg-amber-500 shrink-0 animate-pulse"></span>
              <span>🔒 Controls locked during bulk posting. Do not close this browser tab.</span>
            </div>

            {bulkError && (
              <div className="p-3 bg-rose-50 border border-rose-100 rounded-lg text-rose-700 text-xs text-left dark:bg-rose-950/40 dark:border-rose-900/50 dark:text-rose-455">
                {bulkError}
              </div>
            )}
          </div>
        </div>
      )}

      {/* STEP 8: RESULTS SUMMARY */}
      {activeStep === 8 && validationData && (
        <div className="space-y-6 animate-fade-in">
          <div className="max-w-md mx-auto bg-white rounded-xl border border-slate-200 shadow-sm p-8 space-y-6 text-center dark:bg-slate-900 dark:border-slate-800">
            <div className="mx-auto h-16 w-16 bg-emerald-50 rounded-full flex items-center justify-center text-emerald-600 border border-emerald-100 shadow-sm dark:bg-emerald-950/40 dark:text-emerald-450 dark:border-emerald-900/50">
              <CheckCircle className="h-8 w-8" />
            </div>

            <div className="space-y-1">
              <h4 className="text-md font-bold text-slate-900 uppercase tracking-wider text-xs dark:text-slate-100">Bulk Creation Complete</h4>
              <p className="text-xs text-slate-500 font-medium dark:text-slate-400">Your Zoho Expense batch has completed processing.</p>
            </div>

            <div className="p-5 bg-slate-50 border border-slate-200 rounded-xl text-xs font-semibold text-slate-800 space-y-3.5 text-left dark:bg-slate-950/50 dark:border-slate-800 dark:text-slate-300">
              <div className="flex justify-between">
                <span className="text-slate-400 font-bold uppercase tracking-wider text-[10px] dark:text-slate-550">Total attempted:</span>
                <span>{bulkTotalRows}</span>
              </div>
              <div className="flex justify-between border-t border-slate-200 pt-3 dark:border-slate-800">
                <span className="text-slate-400 font-bold uppercase tracking-wider text-[10px] dark:text-slate-550">Created:</span>
                <span className="text-emerald-700 font-bold dark:text-emerald-455">{bulkCreatedCount}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-400 font-bold uppercase tracking-wider text-[10px] dark:text-slate-550">Failed:</span>
                <span className="text-rose-700 font-bold dark:text-rose-400">{bulkFailedCount}</span>
              </div>
              <div className="flex justify-between border-t border-slate-200 pt-3 dark:border-slate-800">
                <span className="text-slate-400 font-bold uppercase tracking-wider text-[10px] dark:text-slate-550">GST created:</span>
                <span>{bulkRecords.filter(r => r.zoho_status === 'CREATED' && r.gst_type === 'GST').length}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-400 font-bold uppercase tracking-wider text-[10px] dark:text-slate-550">NON-GST created:</span>
                <span>{bulkRecords.filter(r => r.zoho_status === 'CREATED' && r.gst_type === 'NON_GST').length}</span>
              </div>
              <div className="flex justify-between border-t border-slate-200 pt-3 dark:border-slate-800">
                <span className="text-slate-400 font-bold uppercase tracking-wider text-[10px] dark:text-slate-550">Reports submitted:</span>
                <span className="text-rose-600 font-bold dark:text-rose-400">NO</span>
              </div>
            </div>

            <div className="flex flex-col gap-3 pt-3">
              <button
                onClick={() => setShowResultsDrawer(true)}
                className="w-full px-4 py-2.5 bg-slate-800 hover:bg-slate-900 text-white rounded-lg text-xs font-semibold cursor-pointer shadow-xs transition-colors dark:bg-slate-700 dark:hover:bg-slate-600"
              >
                View Outcomes Log
              </button>
              
              {bulkFailedCount > 0 && (
                <a
                  href={api.getErrorReportDownloadUrl(validationData.session.id)}
                  className="w-full px-4 py-2.5 bg-rose-600 hover:bg-rose-700 text-white rounded-lg text-xs font-semibold cursor-pointer text-center block shadow-xs transition-colors"
                >
                  Download Error Spreadsheet
                </a>
              )}
              
              <button
                onClick={handleReset}
                className="w-full px-4 py-2.5 border border-slate-200 hover:bg-slate-50 text-slate-700 rounded-lg text-xs font-semibold cursor-pointer transition-colors dark:border-slate-800 dark:hover:bg-slate-850 dark:text-slate-300"
              >
                Start New Upload Session
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Resume Incomplete Upload Modal */}
      {showResumeDialog && resumeCounts && (
        <div className="fixed inset-0 z-50 overflow-y-auto flex items-center justify-center p-4">
          <div className="fixed inset-0 bg-slate-900/50 backdrop-blur-xs transition-opacity"></div>
          
          <div className="relative bg-white rounded-2xl max-w-md w-full p-6 shadow-2xl border border-slate-250 animate-fade-in space-y-5 text-left dark:bg-slate-900 dark:border-slate-800">
            <div className="flex items-start gap-4">
              <div className="p-2.5 bg-amber-50 text-amber-600 rounded-full shrink-0 dark:bg-amber-950/40 dark:text-amber-400">
                <Clock className="h-6 w-6" />
              </div>
              <div className="space-y-1">
                <h4 className="text-base font-bold text-slate-900 dark:text-slate-100">Incomplete Upload Detected</h4>
                <p className="text-xs text-slate-500 leading-relaxed font-normal dark:text-slate-400">
                  This upload session was previously started but not finished.
                </p>
                <div className="p-3 bg-slate-50 border border-slate-100 rounded-lg text-xs font-semibold text-slate-700 space-y-1.5 mt-3 dark:bg-slate-950/50 dark:border-slate-800 dark:text-slate-300">
                  <div className="flex justify-between">
                    <span>Already Created:</span>
                    <span className="text-emerald-600 font-bold dark:text-emerald-450">{resumeCounts.created}</span>
                  </div>
                  <div className="flex justify-between">
                    <span>Pending Rows:</span>
                    <span className="text-indigo-650 font-bold dark:text-indigo-400">{resumeCounts.pending}</span>
                  </div>
                  {resumeCounts.failed > 0 && (
                    <div className="flex justify-between">
                      <span>Failed Rows:</span>
                      <span className="text-rose-600 font-bold dark:text-rose-455">{resumeCounts.failed}</span>
                    </div>
                  )}
                </div>
              </div>
            </div>
            
            <div className="p-3.5 bg-amber-50 border border-amber-100 rounded-lg text-amber-800 text-[11px] font-normal leading-relaxed dark:bg-amber-950/40 dark:border-amber-900/50 dark:text-amber-400">
              <strong>Notice:</strong> Resuming will only process the remaining <strong>PENDING</strong> rows. Already created rows will never be duplicated.
            </div>

            <div className="flex justify-end gap-3 pt-2">
              <button
                onClick={() => {
                  setShowResumeDialog(false);
                  handleReset();
                }}
                className="px-4 py-2 border border-slate-200 bg-white hover:bg-slate-50 text-slate-700 rounded-lg text-xs font-semibold cursor-pointer dark:border-slate-800 dark:bg-slate-850 dark:hover:bg-slate-800 dark:text-slate-300"
              >
                Cancel & Clear
              </button>
              <button
                onClick={() => {
                  setShowResumeDialog(false);
                  setActiveStep(5); // Go to preview/dry-run review step
                }}
                className="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-xs font-semibold cursor-pointer shadow-md"
              >
                Resume Upload
              </button>
            </div>
          </div>
        </div>
      )}

      {/* View Results List Drawer/Modal */}
      {showResultsDrawer && (
        <div className="fixed inset-0 z-50 overflow-hidden flex items-center justify-center p-4">
          <div className="fixed inset-0 bg-slate-900/50 backdrop-blur-xs transition-opacity animate-fade-in" onClick={() => setShowResultsDrawer(false)}></div>
          
          <div className="relative bg-white rounded-2xl max-w-3xl w-full p-6 shadow-2xl border border-slate-250 animate-fade-in flex flex-col max-h-[85vh] text-left dark:bg-slate-900 dark:border-slate-800">
            <div className="flex items-center justify-between pb-3 border-b border-slate-200 dark:border-slate-800">
              <div>
                <h4 className="font-semibold text-slate-950 dark:text-slate-100">Bulk Upload Outcomes</h4>
                <p className="text-[10px] text-slate-500 font-medium mt-0.5 dark:text-slate-450">Details of creation status for every row in this batch.</p>
              </div>
              <button onClick={() => setShowResultsDrawer(false)} className="text-slate-400 hover:text-slate-600 cursor-pointer dark:text-slate-500 dark:hover:text-slate-350">
                <X className="h-5 w-5" />
              </button>
            </div>
            
            <div className="overflow-y-auto py-4 flex-1">
              <table className="w-full text-left border-collapse text-xs">
                <thead>
                  <tr className="bg-slate-50 border-b border-slate-200 text-slate-500 font-semibold sticky top-0 z-20 dark:bg-slate-900/60 dark:border-slate-800 dark:text-slate-400">
                    <th className="px-3 py-2.5">Row</th>
                    <th className="px-3 py-2.5">Date</th>
                    <th className="px-3 py-2.5">Amount</th>
                    <th className="px-3 py-2.5">Description</th>
                    <th className="px-3 py-2.5">Status</th>
                    <th className="px-3 py-2.5">Zoho Expense ID</th>
                    <th className="px-3 py-2.5">Error Details</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                  {bulkRecords.map((r) => (
                    <tr key={r.id} className="hover:bg-slate-50/50 dark:hover:bg-slate-800/50">
                      <td className="px-3 py-2.5 font-semibold text-slate-400 dark:text-slate-550">{r.original_row_number}</td>
                      <td className="px-3 py-2.5 text-slate-700 dark:text-slate-300">{r.expense_date || 'N/A'}</td>
                      <td className="px-3 py-2.5 text-slate-900 font-bold dark:text-slate-100">
                        {r.amount !== null ? `₹${r.amount.toFixed(2)}` : 'N/A'}
                      </td>
                      <td className="px-3 py-2.5 text-slate-600 truncate max-w-[150px] dark:text-slate-400" title={r.description || ''}>
                        {r.description || 'N/A'}
                      </td>
                      <td className="px-3 py-2.5">
                        <span className={`px-2 py-0.5 rounded-sm text-[9px] font-bold ${
                          r.zoho_status === 'CREATED' ? 'bg-emerald-50 text-emerald-700 border border-emerald-100 dark:bg-emerald-950/50 dark:text-emerald-450 dark:border-emerald-900/50' :
                          r.zoho_status === 'FAILED' ? 'bg-rose-50 text-rose-700 border border-rose-100 dark:bg-rose-950/50 dark:text-rose-455 dark:border-rose-900/50' :
                          r.zoho_status === 'SKIPPED' ? 'bg-amber-50 text-amber-700 border border-amber-100 dark:bg-amber-950/50 dark:text-amber-450 dark:border-amber-900/50' :
                          'bg-slate-100 text-slate-700 border border-slate-200 dark:bg-slate-800 dark:text-slate-300 dark:border-slate-700'
                        }`}>
                          {r.zoho_status || 'PENDING'}
                        </span>
                      </td>
                      <td className="px-3 py-2.5 font-mono text-[10px] text-slate-500 select-all dark:text-slate-450">{r.zoho_expense_id || 'N/A'}</td>
                      <td className="px-3 py-2.5 text-rose-600 max-w-[200px] truncate dark:text-rose-400" title={r.zoho_error || ''}>
                        {r.zoho_error || '-'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            
            <div className="pt-3 border-t border-slate-200 flex justify-end dark:border-slate-800">
              <button 
                onClick={() => setShowResultsDrawer(false)}
                className="px-4 py-2 border border-slate-200 bg-white hover:bg-slate-50 text-slate-700 rounded-lg text-xs font-semibold cursor-pointer dark:border-slate-800 dark:bg-slate-850 dark:hover:bg-slate-800 dark:text-slate-300"
              >
                Close Window
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Test Creation Modal */}
      {showConfirmCreate && selectedRecordForTest && (
        <div className="fixed inset-0 z-50 overflow-y-auto flex items-center justify-center p-4">
          <div className="fixed inset-0 bg-slate-900/50 backdrop-blur-xs transition-opacity" onClick={() => !isCreatingTest && setShowConfirmCreate(false)}></div>

          <div className="relative bg-white rounded-2xl max-w-md w-full p-6 shadow-2xl border border-slate-250 animate-fade-in space-y-6 dark:bg-slate-900 dark:border-slate-800">
            {!creationResult ? (
              <>
                <div className="flex items-center justify-between pb-3 border-b border-slate-100 dark:border-slate-800">
                  <h4 className="text-xs font-bold text-slate-400 uppercase tracking-wider dark:text-slate-500">Test Expense Creation</h4>
                  <button 
                    disabled={isCreatingTest} 
                    onClick={() => setShowConfirmCreate(false)} 
                    className="text-slate-400 hover:text-slate-600 disabled:opacity-50 cursor-pointer dark:text-slate-550 dark:hover:text-slate-400"
                  >
                    <X className="h-4.5 w-4.5" />
                  </button>
                </div>

                <div className="p-4 bg-slate-50 border border-slate-200 rounded-lg text-xs space-y-3 font-semibold text-slate-800 dark:bg-slate-950/50 dark:border-slate-800 dark:text-slate-300">
                  <div className="flex justify-between">
                    <span className="text-slate-400 font-bold uppercase tracking-wider text-[10px] dark:text-slate-500">Excel Row</span>
                    <span className="dark:text-slate-100">{selectedRecordForTest.original_row_number}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-400 font-bold uppercase tracking-wider text-[10px] dark:text-slate-500">Amount</span>
                    <span className="text-slate-950 font-bold dark:text-slate-100">₹{selectedRecordForTest.amount}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-400 font-bold uppercase tracking-wider text-[10px] dark:text-slate-500">Description</span>
                    <span className="text-slate-655 max-w-[200px] truncate dark:text-slate-400" title={selectedRecordForTest.description || ''}>
                      {selectedRecordForTest.description}
                    </span>
                  </div>
                  
                  {/* CATEGORY MAPPING PREVIEW */}
                  <div className="flex justify-between border-t border-slate-150 pt-2 flex-col dark:border-slate-800">
                    <span className="text-slate-400 font-bold uppercase tracking-wider text-[9px] mb-0.5 dark:text-slate-500">Category Mapping</span>
                    <div className="flex justify-between items-center text-[11px]">
                      <span className="text-slate-500 font-medium truncate max-w-[170px] dark:text-slate-400" title={selectedRecordForTest.category || ''}>
                        {selectedRecordForTest.category || 'N/A'}
                      </span>
                      <span className="text-emerald-700 font-bold dark:text-emerald-450">
                        → {mappedCategories[selectedRecordForTest.category || '']?.name || 'N/A'} ✓
                      </span>
                    </div>
                  </div>

                  {/* PAID THROUGH MAPPING PREVIEW */}
                  <div className="flex justify-between border-t border-slate-150 pt-2 flex-col dark:border-slate-800">
                    <span className="text-slate-400 font-bold uppercase tracking-wider text-[9px] mb-0.5 dark:text-slate-500">Paid Through Mapping</span>
                    <div className="flex justify-between items-center text-[11px]">
                      <span className="text-slate-500 font-medium truncate max-w-[170px] dark:text-slate-400" title={selectedRecordForTest.paid_through || ''}>
                        {selectedRecordForTest.paid_through || 'N/A'}
                      </span>
                      <span className="text-emerald-700 font-bold dark:text-emerald-450">
                        → {mappedPaymentModes[selectedRecordForTest.paid_through || '']?.name || 'N/A'} ✓
                      </span>
                    </div>
                  </div>

                  {/* PROJECT MAPPING PREVIEW */}
                  {selectedRecordForTest.project && (
                    <div className="flex justify-between border-t border-slate-150 pt-2 flex-col dark:border-slate-800">
                      <span className="text-slate-400 font-bold uppercase tracking-wider text-[9px] mb-0.5 dark:text-slate-500">Project Mapping</span>
                      <div className="flex justify-between items-center text-[11px]">
                        <span className="text-slate-500 font-medium truncate max-w-[170px] dark:text-slate-400" title={selectedRecordForTest.project || ''}>
                          {selectedRecordForTest.project}
                        </span>
                        <span className="text-emerald-700 font-bold dark:text-emerald-450">
                          → {mappedProjects[selectedRecordForTest.project]?.name || 'N/A'} ✓
                        </span>
                      </div>
                    </div>
                  )}

                  {/* TAX MAPPING PREVIEW */}
                  {selectedRecordForTest.tax_type && (
                    <div className="flex justify-between border-t border-slate-150 pt-2 flex-col dark:border-slate-800">
                      <span className="text-slate-400 font-bold uppercase tracking-wider text-[9px] mb-0.5 dark:text-slate-500">Tax Mapping</span>
                      <div className="flex justify-between items-center text-[11px]">
                        <span className="text-slate-500 font-medium truncate max-w-[170px] dark:text-slate-400" title={selectedRecordForTest.tax_type}>
                          {selectedRecordForTest.tax_type}
                        </span>
                        <span className="text-emerald-700 font-bold dark:text-emerald-450">
                          → {mappedTaxes[selectedRecordForTest.tax_type]?.name || 'N/A'} ✓
                        </span>
                      </div>
                    </div>
                  )}

                  {/* VENDOR PREVIEW */}
                  {selectedRecordForTest.vendor_name && (
                    <div className="flex justify-between border-t border-slate-150 pt-2 flex-col dark:border-slate-800">
                      <span className="text-slate-400 font-bold uppercase tracking-wider text-[9px] mb-0.5 dark:text-slate-500">Vendor Name</span>
                      <div className="flex justify-between items-center text-[11px]">
                        <span className="text-slate-750 font-semibold truncate max-w-[300px] dark:text-slate-300" title={selectedRecordForTest.vendor_name}>
                          {selectedRecordForTest.vendor_name}
                        </span>
                      </div>
                    </div>
                  )}

                  {/* EXPENSE KIND MAPPING PREVIEW */}
                  {selectedRecordForTest.expense_kind && (
                    <div className="flex justify-between border-t border-slate-150 pt-2 flex-col dark:border-slate-800">
                      <span className="text-slate-400 font-bold uppercase tracking-wider text-[9px] mb-0.5 dark:text-slate-500">Expense Kind</span>
                      <div className="flex justify-between items-center text-[11px]">
                        <span className="text-slate-500 font-medium truncate max-w-[170px] dark:text-slate-400" title={selectedRecordForTest.expense_kind}>
                          {selectedRecordForTest.expense_kind}
                        </span>
                        <span className="text-emerald-700 font-bold dark:text-emerald-455">
                          → {mappedExpenseKinds[selectedRecordForTest.expense_kind]?.name || 'N/A'} ✓
                        </span>
                      </div>
                    </div>
                  )}

                  {/* GST/NON-GST MAPPING PREVIEW */}
                  {selectedRecordForTest.gst_type && (
                    <div className="flex justify-between border-t border-slate-150 pt-2 flex-col dark:border-slate-800">
                      <span className="text-slate-400 font-bold uppercase tracking-wider text-[9px] mb-0.5 dark:text-slate-500">GST/Non-GST</span>
                      <div className="flex justify-between items-center text-[11px]">
                        <span className="text-slate-500 font-medium truncate max-w-[170px] dark:text-slate-400" title={selectedRecordForTest.gst_type}>
                          {selectedRecordForTest.gst_type === 'GST' ? 'GST' : 'Non-GST'}
                        </span>
                        <span className="text-emerald-700 font-bold dark:text-emerald-455">
                          → {mappedGstOptions[selectedRecordForTest.gst_type]?.name || 'N/A'} ✓
                        </span>
                      </div>
                    </div>
                  )}

                  <div className="flex justify-between border-t border-slate-150 pt-2 dark:border-slate-800">
                    <span className="text-slate-400 font-bold uppercase tracking-wider text-[10px] dark:text-slate-500">Destination</span>
                    <span className="text-indigo-700 truncate max-w-[200px] dark:text-indigo-400" title={
                      selectedRecordForTest.gst_type === 'GST'
                        ? (reportsList.find(r => r.report_id === gstReportId)?.report_name)
                        : (reportsList.find(r => r.report_id === nongstReportId)?.report_name)
                    }>
                      {selectedRecordForTest.gst_type === 'GST'
                        ? (reportsList.find(r => r.report_id === gstReportId)?.report_name || 'GST Report')
                        : (reportsList.find(r => r.report_id === nongstReportId)?.report_name || 'Non-GST Report')}
                    </span>
                  </div>
                </div>

                <div className="p-3.5 bg-indigo-50 border border-indigo-100 rounded-lg text-xs text-indigo-700 leading-relaxed font-normal dark:bg-indigo-950/40 dark:border-indigo-900/50 dark:text-indigo-400">
                  This will create **ONE** real expense inside the selected Zoho Expense report. The report will **NOT** be submitted.
                </div>

                <div className="flex justify-end gap-3 pt-2">
                  <button
                    disabled={isCreatingTest}
                    onClick={() => setShowConfirmCreate(false)}
                    className="px-4 py-2 border border-slate-200 bg-white hover:bg-slate-50 text-slate-700 rounded-lg text-xs font-semibold cursor-pointer disabled:opacity-50 dark:border-slate-800 dark:bg-slate-850 dark:hover:bg-slate-800 dark:text-slate-300"
                  >
                    Cancel
                  </button>
                  <button
                    disabled={isCreatingTest}
                    onClick={handleExecuteTestCreate}
                    className="inline-flex items-center gap-1.5 px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-xs font-semibold cursor-pointer disabled:opacity-75 disabled:cursor-not-allowed"
                  >
                    {isCreatingTest ? (
                      <>
                        <RefreshCw className="h-3.5 w-3.5 animate-spin" />
                        Creating expense...
                      </>
                    ) : (
                      'CREATE ONE EXPENSE'
                    )}
                  </button>
                </div>
              </>
            ) : creationResult.status === 'success' ? (
              /* State 2: Success Card */
              <>
                <div className="text-center space-y-4">
                  <div className="mx-auto h-12 w-12 bg-emerald-50 rounded-full flex items-center justify-center text-emerald-600 dark:bg-emerald-950/40 dark:text-emerald-450 dark:border-emerald-900/50">
                    <CheckCircle className="h-6 w-6" />
                  </div>
                  <div className="space-y-1">
                    <h4 className="text-base font-bold text-slate-900 uppercase tracking-wide dark:text-slate-100">EXPENSE CREATED ✓</h4>
                    <p className="text-xs text-slate-500 font-medium dark:text-slate-400">Expense created successfully.</p>
                  </div>
                </div>

                <div className="p-4 bg-slate-50 border border-slate-200 rounded-lg text-xs space-y-3 font-semibold text-slate-800 dark:bg-slate-950/50 dark:border-slate-800 dark:text-slate-300">
                  <div className="flex justify-between">
                    <span className="text-slate-400 font-bold uppercase tracking-wider text-[10px] dark:text-slate-550">Excel Row</span>
                    <span className="dark:text-slate-100">{selectedRecordForTest.original_row_number}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-400 font-bold uppercase tracking-wider text-[10px] dark:text-slate-550">Amount</span>
                    <span className="dark:text-slate-100">₹{selectedRecordForTest.amount}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-400 font-bold uppercase tracking-wider text-[10px] dark:text-slate-550">Description</span>
                    <span className="text-slate-655 max-w-[200px] truncate dark:text-slate-400">
                      {selectedRecordForTest.description}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-400 font-bold uppercase tracking-wider text-[10px] dark:text-slate-550">Report</span>
                    <span className="text-indigo-700 truncate max-w-[200px] dark:text-indigo-400" title={
                      selectedRecordForTest.gst_type === 'GST'
                        ? (reportsList.find(r => r.report_id === gstReportId)?.report_name)
                        : (reportsList.find(r => r.report_id === nongstReportId)?.report_name)
                    }>
                      {selectedRecordForTest.gst_type === 'GST'
                        ? (reportsList.find(r => r.report_id === gstReportId)?.report_name)
                        : (reportsList.find(r => r.report_id === nongstReportId)?.report_name)}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-400 font-bold uppercase tracking-wider text-[10px] dark:text-slate-550">Zoho Expense ID</span>
                    <span className="font-mono text-slate-955 text-[11px] bg-slate-100 px-1.5 py-0.5 rounded-sm select-all dark:bg-slate-800 dark:text-slate-100">
                      {creationResult.expense_id}
                    </span>
                  </div>
                  <div className="flex justify-between border-t border-slate-200 pt-2.5 dark:border-slate-850">
                    <span className="text-slate-400 font-bold uppercase tracking-wider text-[10px] dark:text-slate-550">Report Submitted</span>
                    <span className="text-rose-600 font-extrabold text-[10px] bg-rose-50 border border-rose-100 px-2 py-0.5 rounded-full uppercase tracking-wider dark:bg-rose-950/40 dark:border-rose-900/50 dark:text-rose-455">
                      NO
                    </span>
                  </div>
                </div>

                <div className="pt-2 text-center">
                  <button
                    onClick={() => {
                      setShowConfirmCreate(false);
                      setSelectedRecordForTest(null);
                      setCreationResult(null);
                    }}
                    className="w-full py-2 bg-slate-800 hover:bg-slate-900 text-white rounded-lg text-xs font-semibold cursor-pointer shadow-xs dark:bg-slate-700 dark:hover:bg-slate-600"
                  >
                    Done
                  </button>
                </div>
              </>
            ) : (
              /* State 3: Failure Card */
              <>
                <div className="text-center space-y-4">
                  <div className="mx-auto h-12 w-12 bg-rose-50 rounded-full flex items-center justify-center text-rose-600 dark:bg-rose-950/40 dark:text-rose-450 dark:border-rose-900/50">
                    <AlertCircle className="h-6 w-6" />
                  </div>
                  <div className="space-y-1">
                    <h4 className="text-base font-bold text-slate-900 uppercase tracking-wide dark:text-slate-100">CREATION FAILED ❌</h4>
                    <p className="text-xs text-rose-600 font-semibold dark:text-rose-455">Zoho rejected this expense.</p>
                  </div>
                </div>

                <div className="p-4 bg-slate-50 border border-slate-200 rounded-lg text-xs space-y-3 font-semibold text-slate-800 dark:bg-slate-950/50 dark:border-slate-800 dark:text-slate-300">
                  <div className="flex justify-between">
                    <span className="text-slate-400 font-bold uppercase tracking-wider text-[10px] dark:text-slate-550">Excel Row</span>
                    <span className="dark:text-slate-100">{selectedRecordForTest.original_row_number}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-400 font-bold uppercase tracking-wider text-[10px] dark:text-slate-550">Field Involved</span>
                    <span className="text-rose-700 font-bold dark:text-rose-400">{creationResult.field || 'N/A'}</span>
                  </div>
                  <div className="flex flex-col gap-1 text-left border-t border-slate-200 pt-2.5 dark:border-slate-850">
                    <span className="text-slate-400 font-bold uppercase tracking-wider text-[10px] dark:text-slate-550">Safe Error Explanation</span>
                    <span className="text-slate-655 leading-relaxed font-normal mt-1 bg-white p-2.5 border border-slate-200 rounded-lg block max-h-[120px] overflow-y-auto font-mono text-[11px] dark:bg-slate-800 dark:border-slate-700 dark:text-slate-100">
                      {creationResult.message || 'An unknown error occurred.'}
                    </span>
                  </div>
                </div>

                <div className="pt-2 text-center">
                  <button
                    onClick={() => {
                      setShowConfirmCreate(false);
                      setCreationResult(null);
                    }}
                    className="w-full py-2 bg-slate-800 hover:bg-slate-900 text-white rounded-lg text-xs font-semibold cursor-pointer shadow-xs dark:bg-slate-700 dark:hover:bg-slate-600"
                  >
                    Close
                  </button>
                </div>
              </>
            )}
          </div>
        </div>
      )}
    </div>
  );
};
