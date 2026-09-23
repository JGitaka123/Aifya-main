"use client";

import { createContext, useContext, useState, useEffect, useCallback, ReactNode } from "react";
import { api } from "@/lib/api";

export interface AuthUser {
  id: string;
  email: string;
  full_name: string;
  role: string;
  is_active: boolean;
}

interface AuthContextType {
  user: AuthUser | null;
  token: string | null;
  isLoading: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
  isAuthenticated: boolean;
  hasRole: (roles: string[]) => boolean;
  tokenExpiryMinutes: number;
}

const AuthContext = createContext<AuthContextType | null>(null);

/** Set a cookie so Next.js middleware can read the auth token */
function setAuthCookie(token: string | null) {
  if (typeof document === "undefined") return;
  if (token) {
    // Set cookie with SameSite and path
    document.cookie = `aifya_access_token=${token}; path=/; SameSite=Strict; max-age=${60 * 60}`;
  } else {
    // Clear cookie
    document.cookie = "aifya_access_token=; path=/; max-age=0";
  }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [tokenExpiryMinutes, setTokenExpiryMinutes] = useState(15);

  useEffect(() => {
    const savedToken = localStorage.getItem("aifya_access_token");
    const savedUser = localStorage.getItem("aifya_user");
    if (savedToken && savedUser) {
      try {
        setToken(savedToken);
        setUser(JSON.parse(savedUser));
        setAuthCookie(savedToken);
      } catch {
        localStorage.removeItem("aifya_access_token");
        localStorage.removeItem("aifya_user");
        setAuthCookie(null);
      }
    }
    setIsLoading(false);
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    const res = await api.auth.login(email, password);
    setToken(res.access_token);
    setUser(res.user);
    setTokenExpiryMinutes(Math.floor((res.expires_in || 900) / 60));
    localStorage.setItem("aifya_access_token", res.access_token);
    localStorage.setItem("aifya_refresh_token", res.refresh_token);
    localStorage.setItem("aifya_user", JSON.stringify(res.user));
    setAuthCookie(res.access_token);
  }, []);

  const logout = useCallback(() => {
    api.auth.logout().catch(() => { });
    setToken(null);
    setUser(null);
    localStorage.removeItem("aifya_access_token");
    localStorage.removeItem("aifya_refresh_token");
    localStorage.removeItem("aifya_user");
    setAuthCookie(null);
  }, []);

  const hasRole = useCallback(
    (roles: string[]) => {
      if (!user) return false;
      return roles.includes(user.role);
    },
    [user]
  );

  return (
    <AuthContext.Provider
      value={{
        user,
        token,
        isLoading,
        login,
        logout,
        isAuthenticated: !!token,
        hasRole,
        tokenExpiryMinutes,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within an AuthProvider");
  return ctx;
}
