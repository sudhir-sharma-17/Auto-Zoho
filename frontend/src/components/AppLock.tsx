import React, { useState, useEffect, useRef } from 'react';
import { api } from '../services/api';

interface AppLockProps {
  children: React.ReactNode;
}

export const AppLock: React.FC<AppLockProps> = ({ children }) => {
  const [hasPin, setHasPin] = useState<boolean>(false);
  const [isLocked, setIsLocked] = useState<boolean>(true);
  const [pinInput, setPinInput] = useState<string>('');
  const [error, setError] = useState<string | null>(null);
  const [checking, setChecking] = useState<boolean>(true);
  
  const timerRef = useRef<any>(null);
  const INACTIVITY_TIMEOUT = 10 * 60 * 1000; // 10 minutes in ms

  // Check if PIN is configured in the database
  const checkPinStatus = async () => {
    try {
      const res = await api.getLockStatus();
      setHasPin(res.has_pin);
      if (!res.has_pin) {
        setIsLocked(false);
      } else {
        // Check if already unlocked in this session
        const sessUnlocked = sessionStorage.getItem('appUnlocked') === 'true';
        setIsLocked(!sessUnlocked);
      }
    } catch (err) {
      console.error('Failed to query PIN lock status:', err);
    } finally {
      setChecking(false);
    }
  };

  useEffect(() => {
    checkPinStatus();
  }, []);

  // Handle inactivity detection
  useEffect(() => {
    if (!hasPin || isLocked) return;

    const resetTimer = () => {
      if (timerRef.current) clearTimeout(timerRef.current);
      timerRef.current = setTimeout(() => {
        // Lock the application
        sessionStorage.removeItem('appUnlocked');
        setIsLocked(true);
        setPinInput('');
        setError('Session locked due to inactivity.');
      }, INACTIVITY_TIMEOUT);
    };

    // Listen to user interactions
    window.addEventListener('mousemove', resetTimer);
    window.addEventListener('keydown', resetTimer);
    window.addEventListener('mousedown', resetTimer);
    window.addEventListener('scroll', resetTimer);
    
    resetTimer(); // Start timer

    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
      window.removeEventListener('mousemove', resetTimer);
      window.removeEventListener('keydown', resetTimer);
      window.removeEventListener('mousedown', resetTimer);
      window.removeEventListener('scroll', resetTimer);
    };
  }, [hasPin, isLocked]);

  const handleUnlock = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    try {
      const res = await api.verifyPin(pinInput);
      if (res.verified) {
        sessionStorage.setItem('appUnlocked', 'true');
        setIsLocked(false);
        setPinInput('');
      } else {
        setError('Incorrect PIN.');
      }
    } catch (err: any) {
      setError(err.message || 'Incorrect PIN.');
    }
  };

  if (checking) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-900">
        <div className="animate-spin rounded-full h-8 w-8 border-t-2 border-b-2 border-emerald-500"></div>
      </div>
    );
  }

  if (hasPin && isLocked) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-900 px-4 select-none">
        <div className="max-w-md w-full bg-slate-800 border border-slate-700/60 shadow-2xl rounded-2xl p-8 text-center">
          <div className="mx-auto w-12 h-12 bg-slate-700/60 rounded-xl flex items-center justify-center text-emerald-400 mb-5">
            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor" className="w-6 h-6">
              <path strokeLinecap="round" strokeLinejoin="round" d="M16.5 10.5V6.75a4.5 4.5 0 1 0-9 0v3.75m-.75 11.25h10.5a2.25 2.25 0 0 0 2.25-2.25v-6.75a2.25 2.25 0 0 0-2.25-2.25H6.75a2.25 2.25 0 0 0-2.25 2.25v6.75a2.25 2.25 0 0 0 2.25 2.25Z" />
            </svg>
          </div>
          
          <h2 className="text-xl font-bold text-slate-100 mb-2">Application Locked</h2>
          <p className="text-xs text-slate-400 mb-6">Enter your PIN code to access AUTO-ZOHO.</p>
          
          <form onSubmit={handleUnlock} className="space-y-4">
            <div>
              <input
                type="password"
                maxLength={8}
                placeholder="••••"
                value={pinInput}
                onChange={(e) => setPinInput(e.target.value.replace(/\D/g, ''))}
                className="w-full text-center tracking-[1em] font-mono text-xl py-3 px-4 bg-slate-950 border border-slate-700 focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500 rounded-xl text-slate-100 outline-none transition"
                autoFocus
              />
            </div>
            
            {error && (
              <p className="text-xs text-rose-400 font-semibold">{error}</p>
            )}
            
            <button
              type="submit"
              disabled={!pinInput}
              className="w-full py-3 px-4 bg-emerald-600 hover:bg-emerald-500 disabled:bg-slate-700 disabled:text-slate-500 text-slate-100 font-semibold text-xs rounded-xl shadow-lg shadow-emerald-950/20 active:scale-[0.98] outline-none transition"
            >
              Unlock Application
            </button>
          </form>
        </div>
      </div>
    );
  }

  return <>{children}</>;
};
