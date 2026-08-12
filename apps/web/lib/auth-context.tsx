"use client";

import { createContext, useContext, useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { api, setTokens, clearTokens, getAccessToken, ApiError } from "@/lib/api-client";

export interface MeResponse {
  user: { id: string; email: string; full_name: string; is_email_verified: boolean; is_platform_admin: boolean };
  organization: { id: string; name: string; slug: string };
  role: "owner" | "admin" | "member" | "viewer";
}

interface AuthContextValue {
  me: MeResponse | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (data: { email: string; password: string; full_name: string; organization_name: string }) => Promise<void>;
  logout: () => Promise<void>;
  refetchMe: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [me, setMe] = useState<MeResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const router = useRouter();

  const fetchMe = useCallback(async () => {
    if (!getAccessToken()) {
      setMe(null);
      setLoading(false);
      return;
    }
    try {
      const data = await api.get<MeResponse>("/v1/auth/me");
      setMe(data);
    } catch {
      setMe(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchMe();
  }, [fetchMe]);

  const login = useCallback(
    async (email: string, password: string) => {
      const data = await api.post<{ access_token: string; refresh_token: string }>("/v1/auth/login", { email, password });
      setTokens(data.access_token, data.refresh_token);
      await fetchMe();
      router.push("/dashboard");
    },
    [fetchMe, router]
  );

  const register = useCallback(
    async (payload: { email: string; password: string; full_name: string; organization_name: string }) => {
      const data = await api.post<{ access_token: string; refresh_token: string }>("/v1/auth/register", payload);
      setTokens(data.access_token, data.refresh_token);
      await fetchMe();
      router.push("/dashboard");
    },
    [fetchMe, router]
  );

  const logout = useCallback(async () => {
    try {
      await api.post("/v1/auth/logout");
    } catch {
      // logout is best-effort client-side regardless of API result
    }
    clearTokens();
    setMe(null);
    router.push("/login");
  }, [router]);

  return (
    <AuthContext.Provider value={{ me, loading, login, register, logout, refetchMe: fetchMe }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}

export function getAuthErrorMessage(err: unknown): string {
  if (err instanceof ApiError) return err.message;
  return "Something went wrong. Please try again.";
}
