import React, { useEffect, useState } from 'react';
import { 
  FileSpreadsheet, 
  CheckCircle2, 
  AlertCircle, 
  Clock, 
  ArrowRight,
  TrendingUp,
  Inbox
} from 'lucide-react';
import { api } from '../services/api';
import { UploadSession } from '../types';

interface DashboardPageProps {
  onStartUpload: () => void;
}

export const DashboardPage: React.FC<DashboardPageProps> = ({ onStartUpload }) => {
  const [sessions, setSessions] = useState<UploadSession[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.getHistory()
      .then((data) => {
        setSessions(data);
        setLoading(false);
      })
      .catch((err) => {
        setError(err.message);
        setLoading(false);
      });
  }, []);

  const totalProcessed = sessions.reduce((acc, s) => acc + s.total_rows, 0);
  const totalSuccessful = sessions.reduce((acc, s) => acc + s.valid_rows, 0);
  const totalFailed = sessions.reduce((acc, s) => acc + s.invalid_rows, 0);
  const lastSession = sessions.length > 0 ? sessions[0] : null;

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

  if (loading) {
    return (
      <div className="space-y-6">
        <div className="h-8 w-48 bg-slate-200 rounded-md animate-pulse dark:bg-slate-800"></div>
        <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
          {[...Array(4)].map((_, i) => (
            <div key={i} className="h-32 bg-slate-100 rounded-xl border border-slate-200 animate-pulse dark:bg-slate-900 dark:border-slate-800"></div>
          ))}
        </div>
        <div className="h-64 bg-slate-100 rounded-xl border border-slate-200 animate-pulse dark:bg-slate-900 dark:border-slate-800"></div>
      </div>
    );
  }

  if (sessions.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[500px] border border-dashed border-slate-200 bg-white rounded-2xl p-12 text-center shadow-xs dark:bg-slate-900 dark:border-slate-800">
        <div className="p-4 bg-indigo-50 text-indigo-600 rounded-full mb-4 dark:bg-indigo-950/60 dark:text-indigo-400">
          <Inbox className="h-10 w-10" />
        </div>
        <h3 className="text-lg font-semibold text-slate-900 mb-1 dark:text-slate-100">No uploads yet</h3>
        <p className="text-sm text-slate-500 max-w-sm mb-6 dark:text-slate-400">
          Your upload validation sessions history will appear here. Import your first Excel spreadsheet to get started.
        </p>
        <button
          onClick={onStartUpload}
          className="inline-flex items-center gap-2 px-4 py-2.5 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-sm font-medium shadow-xs hover:shadow-md transition-all duration-200 cursor-pointer"
        >
          Start New Upload
          <ArrowRight className="h-4 w-4" />
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-8">
      {/* Title */}
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-xl font-semibold text-slate-900 dark:text-slate-100">Dashboard Summary</h3>
          <p className="text-xs text-slate-500 dark:text-slate-400">Overview of spreadsheet validation runs and local processing performance.</p>
        </div>
        <button
          onClick={onStartUpload}
          className="inline-flex items-center gap-2 px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-sm font-medium shadow-xs hover:shadow-md transition-all duration-200 cursor-pointer"
        >
          New Upload
          <ArrowRight className="h-4 w-4" />
        </button>
      </div>

      {/* Metrics Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
        {/* Total card */}
        <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-xs flex items-center gap-4 dark:bg-slate-900 dark:border-slate-800">
          <div className="p-3 bg-indigo-50 text-indigo-600 rounded-lg dark:bg-indigo-950/60 dark:text-indigo-400">
            <FileSpreadsheet className="h-6 w-6" />
          </div>
          <div>
            <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider dark:text-slate-500">Total Rows</p>
            <h4 className="text-2xl font-bold text-slate-900 mt-1 dark:text-slate-100">{totalProcessed}</h4>
          </div>
        </div>

        {/* Success Card */}
        <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-xs flex items-center gap-4 dark:bg-slate-900 dark:border-slate-800">
          <div className="p-3 bg-emerald-50 text-emerald-600 rounded-lg dark:bg-emerald-950/50 dark:text-emerald-450">
            <CheckCircle2 className="h-6 w-6" />
          </div>
          <div>
            <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider dark:text-slate-500">Valid Rows</p>
            <h4 className="text-2xl font-bold text-slate-900 mt-1 dark:text-slate-100">{totalSuccessful}</h4>
          </div>
        </div>

        {/* Failed Card */}
        <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-xs flex items-center gap-4 dark:bg-slate-900 dark:border-slate-800">
          <div className="p-3 bg-rose-50 text-rose-600 rounded-lg dark:bg-rose-950/60 dark:text-rose-400">
            <AlertCircle className="h-6 w-6" />
          </div>
          <div>
            <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider dark:text-slate-500">Errors Detected</p>
            <h4 className="text-2xl font-bold text-slate-900 mt-1 dark:text-slate-100">{totalFailed}</h4>
          </div>
        </div>

        {/* Last Run Card */}
        <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-xs flex items-center gap-4 dark:bg-slate-900 dark:border-slate-800">
          <div className="p-3 bg-amber-50 text-amber-600 rounded-lg dark:bg-amber-950/60 dark:text-amber-400">
            <Clock className="h-6 w-6" />
          </div>
          <div>
            <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider dark:text-slate-500">Last Upload</p>
            <h4 className="text-sm font-semibold text-slate-700 mt-2 truncate w-36 dark:text-slate-300">
              {lastSession ? formatDate(lastSession.timestamp) : 'N/A'}
            </h4>
          </div>
        </div>
      </div>

      {/* Main Panel - Recent Uploads */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-xs overflow-hidden dark:bg-slate-900 dark:border-slate-800">
        <div className="px-6 py-4 border-b border-slate-200 flex items-center justify-between dark:border-slate-800">
          <h4 className="font-semibold text-slate-950 dark:text-slate-100">Recent Upload Sessions</h4>
          <div className="flex items-center gap-1 text-xs text-slate-500 font-medium dark:text-slate-450">
            <TrendingUp className="h-3.5 w-3.5 text-indigo-500" />
            Active tracking
          </div>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse text-sm">
            <thead>
              <tr className="bg-slate-50 border-b border-slate-200 text-slate-500 font-medium text-xs dark:bg-slate-900/50 dark:border-slate-800 dark:text-slate-400">
                <th className="px-6 py-3">File Name</th>
                <th className="px-6 py-3">Upload Date</th>
                <th className="px-6 py-3">Total Rows</th>
                <th className="px-6 py-3">GST Count</th>
                <th className="px-6 py-3">Non-GST Count</th>
                <th className="px-6 py-3">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
              {sessions.slice(0, 5).map((session) => (
                <tr key={session.id} className="hover:bg-slate-50/50 transition-colors dark:hover:bg-slate-800/50">
                  <td className="px-6 py-4 font-medium text-slate-900 dark:text-slate-200">{session.file_name}</td>
                  <td className="px-6 py-4 text-slate-500 dark:text-slate-450">{formatDate(session.timestamp)}</td>
                  <td className="px-6 py-4 text-slate-600 dark:text-slate-350">{session.total_rows}</td>
                  <td className="px-6 py-4 text-slate-600 dark:text-slate-350">{session.gst_count}</td>
                  <td className="px-6 py-4 text-slate-600 dark:text-slate-350">{session.nongst_count}</td>
                  <td className="px-6 py-4">
                    <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold ${
                      session.status === 'Validated' 
                        ? 'bg-emerald-50 text-emerald-700 border border-emerald-200 dark:bg-emerald-950/50 dark:text-emerald-450 dark:border-emerald-900/50' 
                        : 'bg-rose-50 text-rose-700 border border-rose-200 dark:bg-rose-950/50 dark:text-rose-450 dark:border-rose-900/50'
                    }`}>
                      {session.status}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
