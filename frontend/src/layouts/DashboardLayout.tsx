import React, { useState, useEffect } from 'react';
import { 
  LayoutDashboard, 
  Upload, 
  History as HistoryIcon, 
  Settings as SettingsIcon, 
  Layers,
  AlertTriangle,
  Sun,
  Moon
} from 'lucide-react';
import { api } from '../services/api';

interface DashboardLayoutProps {
  children: React.ReactNode;
  activeTab: string;
  setActiveTab: (tab: string) => void;
  theme: 'light' | 'dark';
  toggleTheme: () => void;
}

export const DashboardLayout: React.FC<DashboardLayoutProps> = ({ 
  children, 
  activeTab, 
  setActiveTab,
  theme,
  toggleTheme
}) => {
  const [connected, setConnected] = useState<boolean | null>(null);
  const [orgName, setOrgName] = useState<string | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [hasError, setHasError] = useState<boolean>(false);

  const fetchStatus = () => {
    api.getZohoStatus()
      .then((status) => {
        setConnected(status.connected);
        setOrgName(status.organization);
        setLoading(false);
        setHasError(false);
      })
      .catch(() => {
        setHasError(true);
        setLoading(false);
      });
  };

  useEffect(() => {
    fetchStatus();
    // Poll connection status every 10 seconds for real-time updates
    const interval = setInterval(fetchStatus, 10000);
    return () => clearInterval(interval);
  }, []);

  const navItems = [
    { id: 'dashboard', label: 'Dashboard', icon: LayoutDashboard },
    { id: 'upload', label: 'Upload Expenses', icon: Upload },
    { id: 'history', label: 'History', icon: HistoryIcon },
    { id: 'settings', label: 'Settings', icon: SettingsIcon },
  ];

  return (
    <div className="flex h-screen bg-slate-50 text-slate-800 dark:bg-slate-950 dark:text-slate-200">
      {/* Sidebar */}
      <aside className="w-64 bg-white border-r border-slate-200 flex flex-col h-full dark:bg-slate-900 dark:border-slate-800">
        {/* Sidebar Header */}
        <div className="h-16 px-6 border-b border-slate-200 flex items-center gap-3 dark:border-slate-800">
          <div className="p-2 bg-indigo-50 text-indigo-600 rounded-lg dark:bg-indigo-900/50 dark:text-indigo-400">
            <Layers className="h-5 w-5" />
          </div>
          <div>
            <h1 className="font-semibold text-slate-900 leading-tight dark:text-slate-100">AUTO-ZOHO</h1>
            <p className="text-[9px] font-bold text-indigo-600 tracking-wider uppercase">Expense Automation</p>
          </div>
        </div>

        {/* Sidebar Nav Links */}
        <nav className="flex-1 px-4 py-6 space-y-1">
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = activeTab === item.id;
            return (
              <button
                key={item.id}
                onClick={() => setActiveTab(item.id)}
                className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all duration-200 cursor-pointer ${
                  isActive 
                    ? 'bg-indigo-50 text-indigo-700 shadow-sm dark:bg-indigo-950/60 dark:text-indigo-450' 
                    : 'text-slate-600 hover:bg-slate-50 hover:text-slate-900 dark:text-slate-400 dark:hover:bg-slate-800 dark:hover:text-slate-100'
                }`}
              >
                <Icon className={`h-4.5 w-4.5 ${isActive ? 'text-indigo-600 dark:text-indigo-400' : 'text-slate-400 group-hover:text-slate-900 dark:text-slate-500'}`} />
                {item.label}
              </button>
            );
          })}
        </nav>

        {/* Connection status indicator */}
        <div className="p-4 border-t border-slate-200 bg-slate-50/50 dark:border-slate-800 dark:bg-slate-900/50">
          <button
            onClick={() => setActiveTab('settings')}
            className="w-full flex items-center gap-2.5 px-3 py-2 rounded-lg bg-white border border-slate-200 hover:border-indigo-300 hover:bg-slate-50/30 transition-all duration-200 text-left shadow-xs cursor-pointer group dark:bg-slate-800 dark:border-slate-700 dark:hover:border-indigo-500"
          >
            {loading ? (
              <>
                <span className="h-2.5 w-2.5 rounded-full bg-amber-400 animate-pulse"></span>
                <span className="text-xs font-semibold text-slate-500 group-hover:text-indigo-600 transition-colors dark:text-slate-400">
                  Connecting...
                </span>
              </>
            ) : hasError ? (
              <>
                <span className="h-2.5 w-2.5 rounded-full bg-rose-500"></span>
                <span className="text-xs font-semibold text-rose-600 group-hover:text-indigo-600 transition-colors">
                  Connection Error
                </span>
              </>
            ) : connected ? (
              <>
                <span className="h-2.5 w-2.5 rounded-full bg-emerald-500 pulse-green shrink-0"></span>
                <div className="overflow-hidden">
                  <span className="text-xs font-bold text-slate-700 group-hover:text-indigo-600 transition-colors block leading-tight dark:text-slate-300 dark:group-hover:text-indigo-400">
                    Zoho Connected
                  </span>
                  <span className="text-[10px] text-slate-400 font-medium truncate block leading-tight max-w-[140px] dark:text-slate-500" title={orgName || ''}>
                    {orgName || 'Active Organization'}
                  </span>
                </div>
              </>
            ) : (
              <>
                <span className="h-2.5 w-2.5 rounded-full bg-slate-400"></span>
                <span className="text-xs font-semibold text-slate-500 group-hover:text-indigo-600 transition-colors dark:text-slate-400">
                  Zoho Not Connected
                </span>
              </>
            )}
          </button>
        </div>
      </aside>

      {/* Main Content Area */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Top Header */}
        <header className="h-16 bg-white border-b border-slate-200 px-8 flex items-center justify-between dark:bg-slate-900 dark:border-slate-800">
          <div>
            <h2 className="text-lg font-bold text-slate-900 dark:text-slate-100 tracking-tight">AUTO-ZOHO</h2>
            <p className="text-xs text-slate-500 font-normal dark:text-slate-400">Smart Zoho Expense Automation</p>
          </div>
          <div className="flex items-center gap-3">
            {/* Theme Toggle Button */}
            <button 
              onClick={toggleTheme}
              className="p-2 text-slate-500 hover:text-slate-900 hover:bg-slate-100 rounded-lg transition-colors cursor-pointer dark:text-slate-400 dark:hover:text-slate-100 dark:hover:bg-slate-800"
              title="Toggle theme"
            >
              {theme === 'dark' ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
            </button>
            <span className="text-xs font-medium bg-slate-100 text-slate-600 px-2.5 py-1 rounded-full border border-slate-200 dark:bg-slate-800 dark:text-slate-300 dark:border-slate-700">
              Phase 4
            </span>
          </div>
        </header>

        {/* Content Pane */}
        <main className="flex-1 overflow-y-auto p-8">
          <div className="max-w-6xl mx-auto animate-fade-in">
            {children}
          </div>
        </main>
      </div>
    </div>
  );
};
