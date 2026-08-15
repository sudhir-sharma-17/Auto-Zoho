import React, { useState, useEffect } from 'react';
import { 
  Database, 
  Lock, 
  Link2, 
  HelpCircle, 
  AlertCircle, 
  Eye, 
  EyeOff,
  RefreshCw,
  CheckCircle,
  AlertTriangle,
  X
} from 'lucide-react';
import { api } from '../services/api';

export const SettingsPage: React.FC = () => {
  const [showPin, setShowPin] = useState(false);
  const [pinValue, setPinValue] = useState('');
  const [hasPin, setHasPin] = useState<boolean>(false);
  const [toastMessage, setToastMessage] = useState<string | null>(null);

  // Zoho states
  const [connected, setConnected] = useState<boolean>(false);
  const [hasCreateScope, setHasCreateScope] = useState<boolean>(true);
  const [orgName, setOrgName] = useState<string | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [testing, setTesting] = useState<boolean>(false);
  const [testResult, setTestResult] = useState<{ status: 'success' | 'error'; message: string } | null>(null);
  const [showDisconnectConfirm, setShowDisconnectConfirm] = useState<boolean>(false);

  useEffect(() => {
    // Detect callbacks from URL query parameters
    const params = new URLSearchParams(window.location.search);
    const connectionResult = params.get('connection');
    if (connectionResult === 'success') {
      setToastMessage("Successfully authorized and connected to Zoho Expense!");
      setTimeout(() => setToastMessage(null), 5000);
      // Clean query params from URL bar
      window.history.replaceState({}, document.title, window.location.pathname);
    } else if (connectionResult === 'error') {
      const errorMsg = params.get('error') || 'OAuth authorization failed.';
      setToastMessage(`Connection failed: ${decodeURIComponent(errorMsg)}`);
      setTimeout(() => setToastMessage(null), 6000);
      window.history.replaceState({}, document.title, window.location.pathname);
    }

    fetchStatus();
  }, []);

  const fetchStatus = () => {
    setLoading(true);
    api.getZohoStatus()
      .then((status) => {
        setConnected(status.connected);
        setOrgName(status.organization);
        
        if (status.connected) {
          api.checkZohoScopes()
            .then((scopeRes) => {
              setHasCreateScope(scopeRes.has_create_scope);
              setLoading(false);
            })
            .catch(() => {
              setHasCreateScope(false);
              setLoading(false);
            });
        } else {
          setHasCreateScope(false);
          setLoading(false);
        }
        
        api.getLockStatus()
          .then((res) => setHasPin(res.has_pin))
          .catch(() => {});
      })
      .catch((err) => {
        setToastMessage(`Failed to read connection status: ${err.message}`);
        setTimeout(() => setToastMessage(null), 4000);
        setLoading(false);
      });
  };

  const handleConnectZoho = () => {
    // Initiate OAuth flow by redirecting browser to backend connect endpoint
    window.location.href = api.getZohoConnectUrl();
  };

  const handleTestConnection = async () => {
    setTesting(true);
    setTestResult(null);
    try {
      const res = await api.testZohoConnection();
      setTestResult({ status: 'success', message: res.message });
      setToastMessage("Connection diagnostics: Active and Healthy!");
      setTimeout(() => setToastMessage(null), 4000);
    } catch (err: any) {
      setTestResult({ status: 'error', message: err.message });
      setToastMessage(`Connection diagnostic failed: ${err.message}`);
      setTimeout(() => setToastMessage(null), 4000);
    } finally {
      setTesting(false);
    }
  };

  const handleDisconnect = async () => {
    try {
      await api.disconnectZoho();
      setConnected(false);
      setOrgName(null);
      setTestResult(null);
      setToastMessage("Revoked Zoho authorization and cleared credentials.");
      setTimeout(() => setToastMessage(null), 4000);
    } catch (err: any) {
      setToastMessage(`Disconnect request failed: ${err.message}`);
      setTimeout(() => setToastMessage(null), 4000);
    } finally {
      setShowDisconnectConfirm(false);
    }
  };

  const handleSavePin = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!pinValue || pinValue.length < 4) {
      setToastMessage("PIN passcode must be at least 4 digits.");
      setTimeout(() => setToastMessage(null), 4000);
      return;
    }
    try {
      if (hasPin) {
        await api.disablePin(pinValue);
        setHasPin(false);
        setPinValue('');
        setToastMessage("PIN passcode disabled successfully.");
      } else {
        await api.setupPin(pinValue);
        setHasPin(true);
        setPinValue('');
        setToastMessage("PIN passcode enabled successfully.");
      }
      setTimeout(() => setToastMessage(null), 4000);
    } catch (err: any) {
      setToastMessage(err.message || "Failed to update security changes.");
      setTimeout(() => setToastMessage(null), 4000);
    }
  };

  return (
    <div className="space-y-8 max-w-3xl relative">
      {/* Title */}
      <div>
        <h3 className="text-xl font-semibold text-slate-900 dark:text-slate-100">Application Settings</h3>
        <p className="text-xs text-slate-500 dark:text-slate-400">Configure connection details, local security policies, and environment parameters.</p>
      </div>

      {/* Floating alert/toast */}
      {toastMessage && (
        <div className="fixed bottom-6 right-6 z-50 bg-indigo-950 text-white text-xs font-semibold px-4 py-3.5 rounded-xl shadow-2xl border border-indigo-800 flex items-center gap-2.5 animate-fade-in max-w-sm dark:bg-slate-950 dark:border-slate-800">
          <AlertCircle className="h-5 w-5 text-indigo-300 shrink-0" />
          <span>{toastMessage}</span>
        </div>
      )}

      {/* Application Diagnostics Card */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-xs overflow-hidden dark:bg-slate-900 dark:border-slate-800">
        <div className="px-6 py-4 border-b border-slate-200 flex items-center gap-3 dark:border-slate-800">
          <Database className="h-5 w-5 text-indigo-500" />
          <h4 className="font-semibold text-slate-950 dark:text-slate-100">Application Environment</h4>
          <span className="ml-auto text-xs font-semibold bg-emerald-50 text-emerald-700 border border-emerald-100 px-2 py-0.5 rounded-sm dark:bg-emerald-950/40 dark:text-emerald-450 dark:border-emerald-900/30">
            Active
          </span>
        </div>
        <div className="p-6 divide-y divide-slate-100 text-sm dark:divide-slate-800">
          <div className="py-3.5 flex justify-between">
            <span className="text-slate-500 font-medium dark:text-slate-400">Software Version</span>
            <span className="font-semibold text-slate-800 dark:text-slate-200">1.0.0 (Phase 3 Build)</span>
          </div>
          <div className="py-3.5 flex justify-between">
            <span className="text-slate-500 font-medium dark:text-slate-400">Environment</span>
            <span className="font-semibold text-slate-800 dark:text-slate-200">Development / Localhost</span>
          </div>
          <div className="py-3.5 flex justify-between">
            <span className="text-slate-500 font-medium dark:text-slate-400">Local Database</span>
            <span className="font-semibold text-slate-800 dark:text-slate-200">SQLite (sqlalchemy.db)</span>
          </div>
        </div>
      </div>

      {/* Zoho Connection Management */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-xs overflow-hidden dark:bg-slate-900 dark:border-slate-800">
        <div className="px-6 py-4 border-b border-slate-200 flex items-center gap-3 dark:border-slate-800">
          <Link2 className="h-5 w-5 text-indigo-500" />
          <h4 className="font-semibold text-slate-955 dark:text-slate-100">Zoho Connection Settings</h4>
          <span className={`ml-auto text-xs font-semibold px-2 py-0.5 rounded-sm border ${
            loading 
              ? 'bg-slate-50 text-slate-400 border-slate-200 dark:bg-slate-800 dark:text-slate-550 dark:border-slate-700' 
              : connected 
                ? 'bg-emerald-50 text-emerald-700 border-emerald-150 dark:bg-emerald-950/40 dark:text-emerald-450 dark:border-emerald-900/30' 
                : 'bg-slate-100 text-slate-600 border-slate-200 dark:bg-slate-800 dark:text-slate-300 dark:border-slate-750'
          }`}>
            {loading ? 'Checking...' : connected ? 'Connected' : 'Not Connected'}
          </span>
        </div>
        <div className="p-6 space-y-6">
          {loading ? (
            <div className="py-6 flex items-center justify-center gap-2 text-xs text-slate-500 font-medium dark:text-slate-405">
              <RefreshCw className="h-4 w-4 animate-spin text-indigo-500" />
              Loading connection parameters...
            </div>
          ) : !connected ? (
            /* Disconnected View */
            <div className="space-y-6">
              <p className="text-xs text-slate-500 leading-relaxed font-normal dark:text-slate-400">
                Connect your Zoho Expense organization securely using Zoho OAuth 2.0.
                No credentials (usernames/passwords) are handled or requested by this application.
              </p>
              <div className="flex items-center justify-between pt-2">
                <div>
                  <p className="text-sm font-semibold text-slate-800 dark:text-slate-200">OAuth Credentials Status</p>
                  <p className="text-xs text-slate-500 mt-0.5 dark:text-slate-450">Integration is currently deactivated.</p>
                </div>
                <button
                  onClick={handleConnectZoho}
                  className="px-4 py-2.5 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-xs font-semibold shadow-xs hover:shadow-md transition-all duration-200 cursor-pointer"
                >
                  Connect Zoho Expense
                </button>
              </div>
            </div>
          ) : (
            /* Connected View */
            <div className="space-y-6">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6 p-4 bg-slate-50 border border-slate-200 rounded-lg dark:bg-slate-950/50 dark:border-slate-800">
                <div>
                  <p className="text-[10px] font-bold text-slate-400 uppercase tracking-wider dark:text-slate-500">Connected Account</p>
                  <p className="text-xs font-semibold text-slate-800 mt-1 dark:text-slate-205">Authorized User Profile</p>
                </div>
                <div>
                  <p className="text-[10px] font-bold text-slate-400 uppercase tracking-wider dark:text-slate-500">Active Organization</p>
                  <p className="text-xs font-bold text-indigo-700 mt-1 dark:text-indigo-400">{orgName || 'N/A'}</p>
                </div>
              </div>

              {!hasCreateScope && (
                <div className="p-4 bg-amber-50 border border-amber-100 rounded-xl space-y-3 dark:bg-amber-955/40 dark:border-amber-900/50">
                  <div className="flex items-start gap-2.5 text-amber-800 dark:text-amber-400">
                    <AlertTriangle className="h-5 w-5 text-amber-600 shrink-0 mt-0.5 animate-pulse" />
                    <div>
                      <h5 className="text-xs font-bold uppercase tracking-wider">Scope Reauthorization Required</h5>
                      <p className="text-xs text-amber-700 mt-1 leading-relaxed dark:text-amber-450">
                        Additional Zoho Expense permission is required (specifically, `ZohoExpense.expense.CREATE` to create expenses).
                      </p>
                    </div>
                  </div>
                  <div className="flex gap-2 justify-end pl-7.5">
                    <button
                      onClick={handleConnectZoho}
                      className="px-3 py-1.5 bg-amber-600 hover:bg-amber-700 text-white rounded-lg text-xs font-semibold shadow-xs transition-colors cursor-pointer"
                    >
                      Reconnect Zoho
                    </button>
                  </div>
                </div>
              )}

              {testResult && (
                <div className={`p-4 rounded-lg border flex items-start gap-2.5 text-xs font-medium ${
                  testResult.status === 'success'
                    ? 'bg-emerald-50 border-emerald-100 text-emerald-800 dark:bg-emerald-950/40 dark:border-emerald-900/50 dark:text-emerald-450'
                    : 'bg-rose-50 border-rose-100 text-rose-800 dark:bg-rose-955/45 dark:border-rose-900/50 dark:text-rose-455'
                }`}>
                  {testResult.status === 'success' ? (
                    <CheckCircle className="h-4.5 w-4.5 text-emerald-600 shrink-0 mt-0.5" />
                  ) : (
                    <AlertCircle className="h-4.5 w-4.5 text-rose-600 shrink-0 mt-0.5" />
                  )}
                  <p>{testResult.message}</p>
                </div>
              )}

              <div className="flex items-center justify-between pt-2">
                <div className="flex gap-3">
                  <button
                    onClick={handleTestConnection}
                    disabled={testing}
                    className="inline-flex items-center gap-1.5 px-4 py-2 border border-slate-200 hover:bg-slate-50 text-slate-700 rounded-lg text-xs font-semibold cursor-pointer dark:border-slate-800 dark:bg-slate-850 dark:hover:bg-slate-800 dark:text-slate-300"
                  >
                    {testing ? <RefreshCw className="h-3.5 w-3.5 animate-spin" /> : null}
                    Test Connection
                  </button>
                  <button
                    onClick={() => setShowDisconnectConfirm(true)}
                    className="px-4 py-2 bg-rose-50 hover:bg-rose-100 text-rose-700 border border-rose-200 rounded-lg text-xs font-semibold cursor-pointer dark:bg-rose-955/20 dark:hover:bg-rose-900/30 dark:text-rose-400 dark:border-rose-900/40"
                  >
                    Disconnect Zoho
                  </button>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Security settings / Application PIN */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-xs overflow-hidden dark:bg-slate-900 dark:border-slate-800">
        <div className="px-6 py-4 border-b border-slate-200 flex items-center gap-3 dark:border-slate-800">
          <Lock className="h-5 w-5 text-indigo-500" />
          <h4 className="font-semibold text-slate-950 dark:text-slate-100">Local Access Security</h4>
          <span className={`ml-auto text-[10px] font-bold uppercase px-2 py-0.5 rounded border ${
            hasPin 
              ? 'bg-emerald-50 text-emerald-700 border-emerald-200 dark:bg-emerald-950/40 dark:text-emerald-450 dark:border-emerald-900/30' 
              : 'bg-slate-100 text-slate-600 border-slate-200 dark:bg-slate-800 dark:text-slate-300 dark:border-slate-700'
          }`}>
            {hasPin ? 'PIN Enabled' : 'PIN Disabled'}
          </span>
        </div>
        <div className="p-6 space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6 p-4 bg-slate-50 border border-slate-200 rounded-lg text-xs dark:bg-slate-955/50 dark:border-slate-800">
            <div>
              <p className="text-[10px] font-bold text-slate-400 uppercase tracking-wider dark:text-slate-500">Credential Storage</p>
              <p className="text-slate-800 mt-1 font-semibold dark:text-slate-200">AES-256 Fernet Encrypted</p>
            </div>
            <div>
              <p className="text-[10px] font-bold text-slate-400 uppercase tracking-wider dark:text-slate-500">Access Scope</p>
              <p className="text-slate-800 mt-1 font-semibold dark:text-slate-200">Minimal (READ Reports/Org)</p>
            </div>
          </div>
          <p className="text-xs text-slate-500 leading-relaxed font-normal dark:text-slate-400">
            {hasPin 
              ? "Your application dashboard access is protected behind a local PIN code. Enter your current PIN below to disable access protection."
              : "Secure the dashboard by locking local settings behind a numeric login PIN. This prevents unauthorized uploads by users sharing this terminal."
            }
          </p>

          <form onSubmit={handleSavePin} className="space-y-4 max-w-sm">
            <div>
              <label className="block text-xs font-bold text-slate-500 uppercase tracking-wider mb-2 dark:text-slate-400">
                {hasPin ? "Enter current PIN to disable" : "Set 4-Digit Passcode PIN"}
              </label>
              <div className="relative">
                <input
                  type={showPin ? "text" : "password"}
                  value={pinValue}
                  onChange={(e) => setPinValue(e.target.value.replace(/\D/g, ''))}
                  maxLength={4}
                  className="w-full bg-slate-50 border border-slate-200 rounded-lg px-3 py-2 text-sm text-slate-800 focus:outline-hidden focus:ring-2 focus:ring-indigo-500 dark:bg-slate-950/50 dark:border-slate-800 dark:text-slate-100"
                  placeholder="Enter 4 digit PIN"
                />
                <button
                  type="button"
                  onClick={() => setShowPin(!showPin)}
                  className="absolute right-3 top-2.5 text-slate-400 hover:text-slate-600 cursor-pointer dark:text-slate-500 dark:hover:text-slate-350"
                >
                  {showPin ? <EyeOff className="h-4.5 w-4.5" /> : <Eye className="h-4.5 w-4.5" />}
                </button>
              </div>
            </div>
            
            <button
              type="submit"
              disabled={pinValue.length < 4}
              className={`px-4 py-2 border rounded-lg text-xs font-semibold transition-colors cursor-pointer ${
                hasPin
                  ? 'border-rose-200 text-rose-700 hover:bg-rose-50 disabled:bg-slate-50 disabled:text-slate-400 disabled:border-slate-200 dark:border-rose-900/40 dark:text-rose-455 dark:hover:bg-rose-955/20 dark:disabled:bg-slate-800 dark:disabled:text-slate-550 dark:disabled:border-slate-750'
                  : 'border-emerald-200 text-emerald-700 hover:bg-emerald-50 disabled:bg-slate-50 disabled:text-slate-400 disabled:border-slate-200 dark:border-emerald-900/40 dark:text-emerald-450 dark:hover:bg-emerald-950/20 dark:disabled:bg-slate-800 dark:disabled:text-slate-550 dark:disabled:border-slate-750'
              }`}
            >
              {hasPin ? "Disable PIN Lock" : "Enable PIN Lock"}
            </button>
          </form>
        </div>
      </div>

      {/* Disconnect Confirmation Modal */}
      {showDisconnectConfirm && (
        <div className="fixed inset-0 z-50 overflow-y-auto flex items-center justify-center p-4">
          {/* Backdrop */}
          <div className="fixed inset-0 bg-slate-900/50 backdrop-blur-xs transition-opacity" onClick={() => setShowDisconnectConfirm(false)}></div>

          {/* Modal box */}
          <div className="relative bg-white rounded-2xl max-w-md w-full p-6 shadow-2xl border border-slate-250 animate-fade-in space-y-5 dark:bg-slate-900 dark:border-slate-800">
            <div className="flex items-start gap-4">
              <div className="p-2.5 bg-rose-50 text-rose-600 rounded-full shrink-0 dark:bg-rose-955/20 dark:text-rose-400">
                <AlertTriangle className="h-6 w-6" />
              </div>
              <div className="space-y-1">
                <h4 className="text-base font-bold text-slate-900 dark:text-slate-100">Disconnect Zoho Expense?</h4>
                <p className="text-xs text-slate-500 leading-relaxed font-normal dark:text-slate-400">
                  This will remove this application's access to your Zoho Expense account. 
                  Your existing Zoho reports and expenses will **not** be deleted.
                </p>
              </div>
            </div>

            <div className="flex justify-end gap-3 pt-2">
              <button
                onClick={() => setShowDisconnectConfirm(false)}
                className="px-4 py-2 border border-slate-200 bg-white hover:bg-slate-50 text-slate-700 rounded-lg text-xs font-semibold cursor-pointer dark:border-slate-800 dark:bg-slate-850 dark:hover:bg-slate-800 dark:text-slate-300"
              >
                Cancel
              </button>
              <button
                onClick={handleDisconnect}
                className="px-4 py-2 bg-rose-600 hover:bg-rose-700 text-white rounded-lg text-xs font-semibold cursor-pointer"
              >
                Disconnect
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
