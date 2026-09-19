import { createContext, useContext, useEffect, useState } from 'react';
import type { ReactNode } from 'react';
import * as api from '../api';
import type { Account } from '../types';

interface AuthState {
  /** `undefined` while the initial `/users/me` check is in flight, `null`
   * once it's known the visitor is signed out, an `Account` once signed in. */
  account: Account | null | undefined;
  refresh: () => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [account, setAccount] = useState<Account | null | undefined>(undefined);

  async function refresh(): Promise<void> {
    try {
      const me = await api.getMe();
      setAccount(me);
    } catch {
      setAccount(null);
    }
  }

  useEffect(() => {
    // The API layer's shared fetch wrapper (issue #30 Implementation
    // Decisions) reads any 401 as "not signed in" uniformly - wired here so
    // a session that expires mid-visit (not just an initial page load)
    // also drops the app back to signed-out state.
    api.setUnauthorizedHandler(() => setAccount(null));
    void refresh();
    return () => api.setUnauthorizedHandler(null);
  }, []);

  async function logout(): Promise<void> {
    try {
      await api.logout();
    } finally {
      setAccount(null);
    }
  }

  return (
    <AuthContext.Provider value={{ account, refresh, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within an AuthProvider');
  return ctx;
}
