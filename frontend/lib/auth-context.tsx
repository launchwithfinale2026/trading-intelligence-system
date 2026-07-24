"use client";

import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { api, ApiError, type User } from "./api";

const TOKEN_STORAGE_KEY = "tis_access_token";

interface AuthContextValue {
  user: User | null;
  token: string | null;
  loading: boolean;
  login: (username: string, password: string) => Promise<void>;
  register: (payload: Parameters<typeof api.register>[0]) => Promise<void>;
  logout: () => void;
  refreshUser: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

function readStoredToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(TOKEN_STORAGE_KEY);
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setToken] = useState<string | null>(readStoredToken);
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  async function loadUser(activeToken: string) {
    try {
      const me = await api.getMe(activeToken);
      setUser(me);
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        localStorage.removeItem(TOKEN_STORAGE_KEY);
        setToken(null);
        setUser(null);
      }
    }
  }

  useEffect(() => {
    (async () => {
      if (token) {
        await loadUser(token);
      }
      setLoading(false);
    })();
    // Intentionally runs once on mount only — token changes from login/logout
    // are handled directly by those functions, not by re-running this effect.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function login(username: string, password: string) {
    const result = await api.login(username, password);
    localStorage.setItem(TOKEN_STORAGE_KEY, result.access_token);
    setToken(result.access_token);
    await loadUser(result.access_token);
  }

  async function register(payload: Parameters<typeof api.register>[0]) {
    await api.register(payload);
    await login(payload.username, payload.password);
  }

  function logout() {
    if (token) {
      api.logout(token).catch(() => {
        // stateless logout — nothing to reconcile if this fails
      });
    }
    localStorage.removeItem(TOKEN_STORAGE_KEY);
    setToken(null);
    setUser(null);
  }

  async function refreshUser() {
    if (token) {
      await loadUser(token);
    }
  }

  return (
    <AuthContext.Provider value={{ user, token, loading, login, register, logout, refreshUser }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return ctx;
}
