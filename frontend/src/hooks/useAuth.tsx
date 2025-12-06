/**
 * Auth context and hooks for Azure AD authentication.
 */

import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  createContext,
  useContext,
  type ReactNode,
  useCallback,
} from "react";
import { api } from "@/lib/api";

/**
 * User role enum matching backend.
 */
export type UserRole = "user" | "admin";

/**
 * User type from API.
 */
export interface User {
  id: string;
  email: string;
  display_name: string;
  role: UserRole;
  is_admin: boolean;
}

/**
 * Auth context value.
 */
interface AuthContextValue {
  user: User | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  isAdmin: boolean;
  login: () => void;
  logout: () => Promise<void>;
  refetch: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

/**
 * Fetch current user from API.
 */
async function fetchCurrentUser(): Promise<User | null> {
  try {
    return await api.get<User>("/auth/me");
  } catch {
    return null;
  }
}

/**
 * Auth provider component.
 */
export function AuthProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient();

  const { data: user, isLoading } = useQuery({
    queryKey: ["auth", "me"],
    queryFn: fetchCurrentUser,
    staleTime: 1000 * 60 * 5, // 5 minutes
    retry: false,
  });

  const login = useCallback(() => {
    // Redirect to backend login endpoint
    window.location.href = `${import.meta.env.VITE_API_URL || ""}/api/v1/auth/login`;
  }, []);

  const logout = useCallback(async () => {
    try {
      await api.post("/auth/logout");
    } finally {
      queryClient.setQueryData(["auth", "me"], null);
      queryClient.clear();
    }
  }, [queryClient]);

  const refetch = useCallback(async () => {
    await queryClient.invalidateQueries({ queryKey: ["auth", "me"] });
  }, [queryClient]);

  const value: AuthContextValue = {
    user: user ?? null,
    isLoading,
    isAuthenticated: !!user,
    isAdmin: user?.role === "admin",
    login,
    logout,
    refetch,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

/**
 * Hook to access auth context.
 */
export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}
