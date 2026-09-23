"use client";

import {
  createContext,
  useContext,
  useEffect,
  useState,
  useCallback,
  type ReactNode,
} from "react";
import {
  BETA_PUBLIC_ACCESS_ENABLED,
  getBetaUser,
} from "@/lib/auth/beta";

interface AuthUser {
  id: string;
  email: string;
  name: string;
  roles: string[];
  facilityId: string;
}

interface AuthContextValue {
  user: AuthUser | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: () => void;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue>({
  user: null,
  isAuthenticated: false,
  isLoading: true,
  login: () => {},
  logout: () => {},
});

/**
 * Authentication provider backed by Aifya's own sign-in.
 * Tokens live in httpOnly cookies set by the BFF route handlers.
 * The client never sees a token, which prevents XSS token theft.
 *
 * @param props.children - Child components
 * @returns Auth context provider
 */
export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(() =>
    BETA_PUBLIC_ACCESS_ENABLED ? getBetaUser() : null,
  );
  const [isLoading, setIsLoading] = useState(!BETA_PUBLIC_ACCESS_ENABLED);

  const login = useCallback(() => {
    if (BETA_PUBLIC_ACCESS_ENABLED) {
      window.location.href = "/";
      return;
    }

    // The BFF resolves the return target and shows the sign-in page.
    const returnTo = `${window.location.pathname}${window.location.search}`;
    window.location.href = `/api/auth/login?returnTo=${encodeURIComponent(returnTo)}`;
  }, []);

  const logout = useCallback(() => {
    if (BETA_PUBLIC_ACCESS_ENABLED) {
      setUser(getBetaUser());
      window.location.href = "/";
      return;
    }

    setUser(null);
    // Server-side logout handler clears the session cookies and redirects
    window.location.href = "/api/auth/logout";
  }, []);

  // Check session on mount by calling the server-side /api/auth/me endpoint
  useEffect(() => {
    if (BETA_PUBLIC_ACCESS_ENABLED) {
      return;
    }

    const checkSession = async () => {
      try {
        const response = await fetch("/api/auth/me", {
          credentials: "include",
        });
        if (response.ok) {
          const data = await response.json();
          if (data.authenticated && data.user) {
            setUser(data.user);
          }
        }
      } catch {
        // Session check failed — user is not authenticated
      } finally {
        setIsLoading(false);
      }
    };

    checkSession();
  }, []);

  return (
    <AuthContext.Provider
      value={{
        user,
        isAuthenticated: !!user,
        isLoading,
        login,
        logout,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

/**
 * Hook to access auth context.
 *
 * @returns Auth context value
 */
export function useAuth(): AuthContextValue {
  return useContext(AuthContext);
}
