import React, { useEffect, useState } from 'react';
import { 
  History, 
  Download, 
  Eye, 
  X, 
  Search,
  CheckCircle,
  AlertCircle,
  ArrowRight,
  TrendingDown,
  ChevronRight,
  Trash2
} from 'lucide-react';
import { api } from '../services/api';
import { UploadSession, UploadSessionDetail } from '../types';

export const HistoryPage: React.FC = () => {
  const [sessions, setSessions] = useState<UploadSession[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  
  // Drawer state for viewing details
  const [selectedSessionId, setSelectedSessionId] = useState<number | null>(null);
  const [sessionDetail, setSessionDetail] = useState<UploadSessionDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState<boolean>(false);
  const [detailSearch, setDetailSearch] = useState<string>('');
  const [detailStatus, setDetailStatus] = useState<string>('ALL');

  useEffect(() => {
    fetchHistory();
  }, []);

  const fetchHistory = () => {
    setLoading(true);
    api.getHistory()
      .then((data) => {
        setSessions(data);
        setLoading(false);
      })
      .catch((err) => {
        setError(err.message);
        setLoading(false);
      });
  };

  const handleViewDetails = async (id: number) => {
    setSelectedSessionId(id);
    setDetailLoading(true);
    setSessionDetail(null);
    setDetailSearch('');
    setDetailStatus('ALL');

    try {
      const data = await api.getSessionDetails(id);
      setSessionDetail(data);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setDetailLoading(false);
    }
  };

  // Re-fetch details when filters are changed
  const handleFilterChange = async (status: string, search: string) => {
    if (!selectedSessionId) return;
    setDetailLoading(true);
    try {
      const data = await api.getSessionDetails(selectedSessionId, {
        status: status === 'ALL' ? undefined : status,
        search: search.trim() === '' ? undefined : search
      });
      setSessionDetail(data);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setDetailLoading(false);
    }
  };

  const closeDrawer = () => {
    setSelectedSessionId(null);
    setSessionDetail(null);
  };

  const formatDate = (dateStr: string) => {
    const d = new Date(dateStr);
    return d.toLocaleString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  const handleDownloadErrors = (id: number) => {
    const url = api.getErrorDownloadUrl(id);
    window.open(url, '_blank');
  };

  const handleDeleteSession = async (id: number) => {
    if (!window.confirm("Are you sure you want to permanently delete this validation session and all its records? This cannot be undone.")) {
      return;
    }
    try {
      await api.deleteSession(id);
      fetchHistory();
    } catch (err: any) {
      alert(err.message || "Failed to delete session.");
    }
  };

  const handleClearAll = async () => {
    if (!window.confirm("Are you sure you want to permanently clear the entire upload history and delete all records? This cannot be undone.")) {
      return;
    }
    try {
      await api.clearHistory();
      fetchHistory();
    } catch (err: any) {
      alert(err.message || "Failed to clear history.");
    }
  };

  if (loading) {
    return (
      <div className="space-y-6">
        <div className="h-8 w-48 bg-slate-200 rounded-md animate-pulse dark:bg-slate-800"></div>
        <div className="h-64 bg-slate-100 rounded-xl border border-slate-200 animate-pulse dark:bg-slate-900/50 dark:border-slate-800"></div>
      </div>
    );
  }

  return (
    <div className="relative">
      <div className="space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-xl font-semibold text-slate-900 dark:text-slate-100">Upload History</h3>
            <p className="text-xs text-slate-500 dark:text-slate-400">Inspect historical validation sessions and recover error reports.</p>
          </div>
          {sessions.length > 0 && (
            <button
              onClick={handleClearAll}
              className="inline-flex items-center gap-1.5 px-3 py-2 bg-rose-50 text-rose-700 border border-rose-200 hover:bg-rose-100 rounded-lg text-xs font-semibold transition-colors cursor-pointer dark:bg-rose-955/20 dark:text-rose-455 dark:border-rose-900/40 dark:hover:bg-rose-900/30"
            >
              <Trash2 className="h-3.5 w-3.5" />
              Clear All History
            </button>
          )}
        </div>

        {/* Sessions Table */}
        <div className="bg-white rounded-xl border border-slate-200 shadow-xs overflow-hidden dark:bg-slate-900 dark:border-slate-800">
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse text-sm">
              <thead>
                <tr className="bg-slate-50 border-b border-slate-200 text-slate-500 font-medium text-xs dark:bg-slate-900/60 dark:border-slate-800 dark:text-slate-400">
                  <th className="px-6 py-3.5">File Name</th>
                  <th className="px-6 py-3.5">Processed Date</th>
                  <th className="px-6 py-3.5">Total Rows</th>
                  <th className="px-6 py-3.5">Valid Rows</th>
                  <th className="px-6 py-3.5">Invalid Rows</th>
                  <th className="px-6 py-3.5">Status</th>
                  <th className="px-6 py-3.5 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                {sessions.length > 0 ? (
                  sessions.map((session) => (
                    <tr key={session.id} className="hover:bg-slate-50/50 transition-colors dark:hover:bg-slate-800/50">
                      <td className="px-6 py-4 font-semibold text-slate-900 dark:text-slate-100">{session.file_name}</td>
                      <td className="px-6 py-4 text-slate-500 dark:text-slate-400">{formatDate(session.timestamp)}</td>
                      <td className="px-6 py-4 text-slate-600 font-medium dark:text-slate-300">{session.total_rows}</td>
                      <td className="px-6 py-4 text-emerald-600 font-semibold dark:text-emerald-450">{session.valid_rows}</td>
                      <td className="px-6 py-4 text-rose-600 font-semibold dark:text-rose-400">{session.invalid_rows}</td>
                      <td className="px-6 py-4">
                        <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold ${
                          session.status === 'Validated' 
                            ? 'bg-emerald-50 text-emerald-700 border border-emerald-200 dark:bg-emerald-950/40 dark:text-emerald-450 dark:border-emerald-900/30' 
                            : 'bg-rose-50 text-rose-700 border border-rose-200 dark:bg-rose-955/40 dark:text-rose-455 dark:border-rose-900/30'
                        }`}>
                          {session.status}
                        </span>
                      </td>
                      <td className="px-6 py-4 text-right">
                        <div className="flex justify-end gap-2">
                          <button
                            onClick={() => handleViewDetails(session.id)}
                            className="inline-flex items-center gap-1 px-2.5 py-1.5 border border-slate-200 hover:bg-slate-50 text-slate-600 hover:text-slate-900 rounded-md text-xs font-medium transition-colors cursor-pointer dark:border-slate-800 dark:bg-slate-850 dark:hover:bg-slate-800 dark:text-slate-350 dark:hover:text-slate-100"
                          >
                            <Eye className="h-3.5 w-3.5" />
                            Details
                          </button>
                          {session.invalid_rows > 0 && (
                            <button
                              onClick={() => handleDownloadErrors(session.id)}
                              className="inline-flex items-center gap-1 px-2.5 py-1.5 bg-rose-50 text-rose-700 border border-rose-200 hover:bg-rose-100 rounded-md text-xs font-semibold transition-colors cursor-pointer dark:bg-rose-955/20 dark:text-rose-455 dark:border-rose-900/40 dark:hover:bg-rose-900/30"
                              title="Download Error Report"
                            >
                              <Download className="h-3.5 w-3.5" />
                              Errors
                            </button>
                          )}
                          <button
                            onClick={() => handleDeleteSession(session.id)}
                            className="inline-flex items-center gap-1 px-2.5 py-1.5 border border-rose-200 bg-white hover:bg-rose-50 text-rose-600 hover:text-rose-700 rounded-md text-xs font-medium transition-colors cursor-pointer dark:border-rose-905/30 dark:bg-slate-850 dark:hover:bg-rose-955/10 dark:text-rose-455"
                            title="Delete Session"
                          >
                            <Trash2 className="h-3.5 w-3.5" />
                            Delete
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))
                ) : (
                  <tr>
                    <td colSpan={7} className="px-6 py-12 text-center text-slate-400 font-medium dark:text-slate-500">
                      No validation logs are stored.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      {/* Slide-over details Drawer */}
      {selectedSessionId !== null && (
        <div className="fixed inset-0 overflow-hidden z-50 flex justify-end">
          {/* Backdrop */}
          <div 
            onClick={closeDrawer}
            className="absolute inset-0 bg-slate-900/40 backdrop-blur-xs transition-opacity duration-300" 
          />

          {/* Drawer Panel */}
          <div className="relative w-full max-w-4xl bg-white h-full shadow-2xl flex flex-col z-10 animate-fade-in dark:bg-slate-900">
            {/* Header */}
            <div className="p-6 border-b border-slate-200 flex items-center justify-between bg-slate-50 dark:bg-slate-900/40 dark:border-slate-800">
              <div>
                <h3 className="text-base font-bold text-slate-900 dark:text-slate-100">Upload Session Details</h3>
                {sessionDetail && (
                  <p className="text-xs text-slate-500 font-medium mt-1 dark:text-slate-400">
                    {sessionDetail.file_name} • {formatDate(sessionDetail.timestamp)}
                  </p>
                )}
              </div>
              <button 
                onClick={closeDrawer}
                className="p-1.5 border border-slate-200 bg-white hover:bg-slate-100 text-slate-500 hover:text-slate-800 rounded-lg transition-colors cursor-pointer dark:border-slate-800 dark:bg-slate-850 dark:hover:bg-slate-800 dark:text-slate-400 dark:hover:text-slate-200"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            {/* Metrics values block */}
            {sessionDetail && (
              <div className="px-6 py-4 border-b border-slate-100 grid grid-cols-5 gap-4 bg-white dark:bg-slate-900 dark:border-slate-800">
                <div>
                  <p className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider dark:text-slate-550">Total Rows</p>
                  <p className="text-sm font-bold text-slate-800 mt-0.5 dark:text-slate-200">{sessionDetail.total_rows}</p>
                </div>
                <div>
                  <p className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider dark:text-slate-555">GST Count</p>
                  <p className="text-sm font-bold text-slate-800 mt-0.5 dark:text-slate-200">{sessionDetail.gst_count}</p>
                </div>
                <div>
                  <p className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider dark:text-slate-555">Non-GST Count</p>
                  <p className="text-sm font-bold text-slate-800 mt-0.5 dark:text-slate-200">{sessionDetail.nongst_count}</p>
                </div>
                <div>
                  <p className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider dark:text-slate-555">Valid Rows</p>
                  <p className="text-sm font-bold text-emerald-600 mt-0.5 dark:text-emerald-450">{sessionDetail.valid_rows}</p>
                </div>
                <div>
                  <p className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider dark:text-slate-555">Errors</p>
                  <p className="text-sm font-bold text-rose-600 mt-0.5 dark:text-rose-400">{sessionDetail.invalid_rows}</p>
                </div>
              </div>
            )}

            {/* Filter controls inside drawer */}
            <div className="px-6 py-4 border-b border-slate-100 flex gap-4 items-center justify-between bg-slate-50/50 dark:bg-slate-950/20 dark:border-slate-800">
              <div className="flex border border-slate-200 bg-white rounded-lg p-0.5 gap-1 dark:border-slate-800 dark:bg-slate-850">
                <button
                  onClick={() => {
                    setDetailStatus('ALL');
                    handleFilterChange('ALL', detailSearch);
                  }}
                  className={`px-3 py-1 rounded-md text-[11px] font-semibold cursor-pointer transition-colors ${
                    detailStatus === 'ALL' ? 'bg-indigo-50 text-indigo-700 shadow-xs dark:bg-indigo-950 dark:text-indigo-400' : 'text-slate-600 dark:text-slate-400 hover:text-slate-800 dark:hover:text-slate-200'
                  }`}
                >
                  All
                </button>
                <button
                  onClick={() => {
                    setDetailStatus('VALID');
                    handleFilterChange('VALID', detailSearch);
                  }}
                  className={`px-3 py-1 rounded-md text-[11px] font-semibold cursor-pointer transition-colors ${
                    detailStatus === 'VALID' ? 'bg-emerald-50 text-emerald-700 shadow-xs dark:bg-emerald-950 dark:text-emerald-400' : 'text-slate-600 dark:text-slate-400 hover:text-slate-800 dark:hover:text-slate-200'
                  }`}
                >
                  Valid
                </button>
                <button
                  onClick={() => {
                    setDetailStatus('INVALID');
                    handleFilterChange('INVALID', detailSearch);
                  }}
                  className={`px-3 py-1 rounded-md text-[11px] font-semibold cursor-pointer transition-colors ${
                    detailStatus === 'INVALID' ? 'bg-rose-50 text-rose-700 shadow-xs dark:bg-rose-955 dark:text-rose-455' : 'text-slate-600 dark:text-slate-400 hover:text-slate-800 dark:hover:text-slate-200'
                  }`}
                >
                  Errors
                </button>
              </div>

              <div className="relative w-64">
                <Search className="absolute left-2.5 top-2.5 h-3.5 w-3.5 text-slate-400 dark:text-slate-500" />
                <input
                  type="text"
                  placeholder="Search description, category..."
                  value={detailSearch}
                  onChange={(e) => {
                    setDetailSearch(e.target.value);
                    handleFilterChange(detailStatus, e.target.value);
                  }}
                  className="w-full bg-white border border-slate-200 rounded-lg pl-8 pr-4 py-1.5 text-xs text-slate-800 placeholder-slate-400 focus:outline-hidden focus:ring-1 focus:ring-indigo-500 dark:bg-slate-900 dark:border-slate-800 dark:text-slate-100 dark:placeholder-slate-500"
                />
              </div>
            </div>

            {/* List Rows Table */}
            <div className="flex-1 overflow-y-auto p-6 bg-white dark:bg-slate-900">
              {detailLoading ? (
                <div className="space-y-4">
                  {[...Array(5)].map((_, i) => (
                    <div key={i} className="h-10 bg-slate-100 rounded-md animate-pulse dark:bg-slate-800"></div>
                  ))}
                </div>
              ) : sessionDetail ? (
                <div className="border border-slate-200 rounded-lg overflow-hidden dark:border-slate-800">
                  <table className="w-full text-left border-collapse text-xs">
                    <thead>
                      <tr className="bg-slate-50 border-b border-slate-200 text-slate-500 font-semibold dark:bg-slate-900/60 dark:border-slate-800 dark:text-slate-400">
                        <th className="px-3 py-2.5 w-12">Row</th>
                        <th className="px-3 py-2.5 w-24">Date</th>
                        <th className="px-3 py-2.5 w-20">Amount</th>
                        <th className="px-3 py-2.5">Description</th>
                        <th className="px-3 py-2.5 w-20">GST</th>
                        <th className="px-3 py-2.5">Category</th>
                        <th className="px-3 py-2.5">Vendor</th>
                        <th className="px-3 py-2.5 w-16 text-center">Status</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                      {sessionDetail.records.map((rec) => {
                        const hasErrors = rec.status === 'INVALID';
                        return (
                          <React.Fragment key={rec.id}>
                            <tr className={`${hasErrors ? 'bg-rose-500/5 dark:bg-rose-955/5' : 'hover:bg-slate-50/25 dark:hover:bg-slate-800/30'}`}>
                              <td className="px-3 py-3 font-semibold text-slate-400 dark:text-slate-550">{rec.original_row_number}</td>
                              <td className="px-3 py-3 font-medium text-slate-700 dark:text-slate-300">{rec.expense_date || 'N/A'}</td>
                              <td className="px-3 py-3 font-bold text-slate-900 dark:text-slate-100">
                                {rec.amount !== null ? `₹${rec.amount.toFixed(2)}` : 'N/A'}
                              </td>
                              <td className="px-3 py-3 text-slate-700 dark:text-slate-300">{rec.description || 'N/A'}</td>
                              <td className="px-3 py-3">
                                <span className={`px-1.5 py-0.5 rounded-sm text-[9px] font-semibold ${
                                  rec.gst_type === 'GST' 
                                    ? 'bg-indigo-50 text-indigo-700 border border-indigo-100 dark:bg-indigo-950/50 dark:text-indigo-400 dark:border-indigo-900/50' 
                                    : 'bg-slate-100 text-slate-700 border border-slate-200 dark:bg-slate-800 dark:text-slate-300 dark:border-slate-700'
                                }`}>
                                  {rec.gst_type || 'N/A'}
                                </span>
                              </td>
                              <td className="px-3 py-3 text-slate-600 dark:text-slate-400">{rec.category || 'N/A'}</td>
                              <td className="px-3 py-3 text-slate-600 font-medium dark:text-slate-400">{rec.vendor_name || 'N/A'}</td>
                              <td className="px-3 py-3 text-center">
                                <div className="flex justify-center">
                                  {hasErrors ? (
                                    <AlertCircle className="h-4 w-4 text-rose-500 dark:text-rose-455" />
                                  ) : (
                                    <CheckCircle className="h-4 w-4 text-emerald-500" />
                                  )}
                                </div>
                              </td>
                            </tr>
                            {hasErrors && rec.errors && (
                              <tr className="bg-rose-50/10 dark:bg-rose-955/5">
                                <td colSpan={8} className="px-3 py-1.5 border-t border-rose-50/50 dark:border-rose-900/20">
                                  <div className="pl-6 text-rose-700 text-[10px] font-medium dark:text-rose-400">
                                    <span className="font-bold text-rose-800 dark:text-rose-350">Errors: </span>
                                    {rec.errors.split(';').join(', ')}
                                  </div>
                                </td>
                              </tr>
                            )}
                          </React.Fragment>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              ) : (
                <p className="text-center py-12 text-slate-400 font-medium dark:text-slate-500">Failed to load detail records.</p>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
