import { createContext, ReactNode, useCallback, useContext, useEffect, useState } from "react";
import { get, post } from "./api";

export interface AuthUser { username: string; display_name: string | null }
interface AuthCtx {
  user: AuthUser | null;
  loading: boolean;
  login: (username: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
}

const Ctx = createContext<AuthCtx | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    get<AuthUser>("/api/auth/me")
      .then((u) => { if (!cancelled) setUser(u); })
      .catch(() => { if (!cancelled) setUser(null); })
      .finally(() => { if (!cancelled) setLoading(false); });
    // api.ts fires this when any request comes back 401 (e.g. the session expired)
    const onExpired = () => setUser(null);
    window.addEventListener("auth:expired", onExpired);
    return () => { cancelled = true; window.removeEventListener("auth:expired", onExpired); };
  }, []);

  const login = useCallback(async (username: string, password: string) => {
    setUser(await post<AuthUser>("/api/auth/login", { username, password }));
  }, []);

  const logout = useCallback(async () => {
    try { await post("/api/auth/logout"); } finally { setUser(null); }
  }, []);

  return <Ctx.Provider value={{ user, loading, login, logout }}>{children}</Ctx.Provider>;
}

export function useAuth(): AuthCtx {
  const c = useContext(Ctx);
  if (!c) throw new Error("useAuth must be used inside <AuthProvider>");
  return c;
}
