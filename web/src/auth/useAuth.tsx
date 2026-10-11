import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { admin } from "../api/admin";
import { identity } from "../api/identity";
import type { User, UserRole } from "../api/types";
import { clearTokens, getTokens } from "./tokenStore";

export interface AuthState {
  ready: boolean;
  /** True when an end-user (anonymous) token is present. */
  anon: boolean;
  anonId: string | null;
  isAdmin: boolean;
  role: UserRole | null;
  ensureAnon: () => Promise<void>;
  adminLogin: (email: string, password: string) => Promise<void>;
  adminLogout: () => void;
}

const Ctx = createContext<AuthState | null>(null);
const ROLE_KEY = "ubuzima.admin.role";

function readRole(): UserRole | null {
  try { const r = localStorage.getItem(ROLE_KEY); return r === "admin" || r === "reviewer" || r === "user" ? r : null; }
  catch { return null; }
}
function writeRole(r: UserRole | null): void {
  try { if (r) localStorage.setItem(ROLE_KEY, r); else localStorage.removeItem(ROLE_KEY); } catch { /* unavailable */ }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [ready, setReady] = useState(false);
  const [anon, setAnon] = useState(() => !!getTokens("user"));
  const [anonId, setAnonId] = useState<string | null>(null);
  const [isAdmin, setIsAdmin] = useState(() => !!getTokens("admin"));
  const [role, setRole] = useState<UserRole | null>(() => (getTokens("admin") ? readRole() : null));

  const ensureAnon = useCallback(async () => {
    if (getTokens("user")) { setAnon(true); return; }
    const s = await identity.anon();
    setAnonId(s.anon_id);
    setAnon(true);
  }, []);

  useEffect(() => {
    let live = true;
    ensureAnon().catch(() => { /* offline: surfaced by later calls */ }).finally(() => { if (live) setReady(true); });
    return () => { live = false; };
  }, [ensureAnon]);

  const adminLogin = useCallback(async (email: string, password: string) => {
    await admin.login(email, password);
    setIsAdmin(true);
    try {
      const users = await admin.listUsers();
      const me = users.find((u: User) => u.email?.toLowerCase() === email.toLowerCase());
      const r = me?.role ?? "admin";
      writeRole(r); setRole(r);
    } catch { setRole("admin"); writeRole("admin"); }
  }, []);

  const adminLogout = useCallback(() => {
    clearTokens("admin"); writeRole(null); setIsAdmin(false); setRole(null);
  }, []);

  const value = useMemo<AuthState>(
    () => ({ ready, anon, anonId, isAdmin, role, ensureAnon, adminLogin, adminLogout }),
    [ready, anon, anonId, isAdmin, role, ensureAnon, adminLogin, adminLogout],
  );
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useAuth(): AuthState {
  const v = useContext(Ctx);
  if (!v) throw new Error("useAuth must be used within AuthProvider");
  return v;
}
