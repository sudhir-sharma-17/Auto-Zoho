import React, { useState, useEffect } from 'react';
import { DashboardLayout } from './layouts/DashboardLayout';
import { DashboardPage } from './pages/DashboardPage';
import { UploadPage } from './pages/UploadPage';
import { HistoryPage } from './pages/HistoryPage';
import { SettingsPage } from './pages/SettingsPage';
import { AppLock } from './components/AppLock';
import { LoginPage } from './pages/LoginPage';
import { InitializePasswordPage } from './pages/InitializePasswordPage';
import { ForgotPasswordPage } from './pages/ForgotPasswordPage';
import { api } from './services/api';

export const App: React.FC = () => {
  const [activeTab, setActiveTab] = useState<string>('dashboard');
  const [theme, setTheme] = useState<'light' | 'dark'>(() => {
    const saved = localStorage.getItem('theme');
    if (saved === 'dark' || (!saved && window.matchMedia('(prefers-color-scheme: dark)').matches)) {
      return 'dark';
    }
    return 'light';
  });

  // Authentication State
  const [checkingAuth, setCheckingAuth] = useState<boolean>(true);
  const [initialized, setInitialized] = useState<boolean>(false);
  const [authenticated, setAuthenticated] = useState<boolean>(false);
  const [adminUsername, setAdminUsername] = useState<string>('');
  const [adminEmail, setAdminEmail] = useState<string>('');
  const [authView, setAuthView] = useState<'login' | 'forgot-password' | 'initialize-password'>('login');

  const checkAuth = async () => {
    try {
      const status = await api.getAuthStatus();
      setInitialized(status.initialized);
      setAuthenticated(status.authenticated);
      setAdminUsername(status.username || '');
      setAdminEmail(status.email || '');
      
      if (!status.initialized) {
        setAuthView('initialize-password');
      } else if (!status.authenticated) {
        setAuthView('login');
      }
    } catch (err) {
      console.error('Auth verification failed:', err);
      setAuthView('login');
    } finally {
      setCheckingAuth(false);
    }
  };

  useEffect(() => {
    checkAuth();

    // Catch 401 unauthorized calls globally and redirect to login
    const handleUnauthorized = () => {
      setAuthenticated(false);
      setAuthView('login');
    };
    window.addEventListener('auth-unauthorized', handleUnauthorized);
    return () => {
      window.removeEventListener('auth-unauthorized', handleUnauthorized);
    };
  }, []);

  useEffect(() => {
    if (theme === 'dark') {
      document.documentElement.classList.add('dark');
      localStorage.setItem('theme', 'dark');
    } else {
      document.documentElement.classList.remove('dark');
      localStorage.setItem('theme', 'light');
    }
  }, [theme]);

  const toggleTheme = () => {
    setTheme(prev => prev === 'light' ? 'dark' : 'light');
  };

  const handleLogout = async () => {
    try {
      await api.logout();
    } catch (err) {
      console.error('Failed to log out:', err);
    }
    setAuthenticated(false);
    setAuthView('login');
  };

  const renderContent = () => {
    switch (activeTab) {
      case 'dashboard':
        return <DashboardPage onStartUpload={() => setActiveTab('upload')} />;
      case 'upload':
        return <UploadPage onNavigateToTab={setActiveTab} />;
      case 'history':
        return <HistoryPage />;
      case 'settings':
        return <SettingsPage />;
      default:
        return <DashboardPage onStartUpload={() => setActiveTab('upload')} />;
    }
  };

  // 1. Loading Screen
  if (checkingAuth) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-900">
        <div className="flex flex-col items-center gap-3">
          <div className="animate-spin rounded-full h-8 w-8 border-t-2 border-b-2 border-indigo-500"></div>
          <span className="text-xs text-slate-400 font-semibold tracking-wide">Securing Session...</span>
        </div>
      </div>
    );
  }

  // 2. Authentication Flow
  if (!authenticated) {
    if (authView === 'initialize-password') {
      return (
        <InitializePasswordPage 
          username={adminUsername} 
          email={adminEmail} 
          onInitializationSuccess={checkAuth} 
        />
      );
    }
    if (authView === 'forgot-password') {
      return (
        <ForgotPasswordPage 
          onBackToLogin={() => setAuthView('login')} 
        />
      );
    }
    return (
      <LoginPage 
        onLoginSuccess={checkAuth} 
        onNavigateToForgotPassword={() => setAuthView('forgot-password')} 
      />
    );
  }

  // 3. Authenticated App Context
  return (
    <AppLock>
      <DashboardLayout 
        activeTab={activeTab} 
        setActiveTab={setActiveTab} 
        theme={theme} 
        toggleTheme={toggleTheme}
        onLogout={handleLogout}
      >
        {renderContent()}
      </DashboardLayout>
    </AppLock>
  );
};

export default App;

