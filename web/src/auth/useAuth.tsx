import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { admin } from "../api/admin";
import { identity } from "../api/identity";
import type { AnonSession, User, UserRole } from "../api/types";
import { onAuthExpired } from "../api/client";
import { clearTokens, getAnonId, getTokens } from "./tokenStore";

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

let inflightAnon: Promise<AnonSession> | null = null;
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
  const [anonId, setAnonId] = useState<string | null>(() => getAnonId());
  const [isAdmin, setIsAdmin] = useState(() => !!getTokens("admin"));
  const [role, setRole] = useState<UserRole | null>(() => (getTokens("admin") ? readRole() : null));

  const ensureAnon = useCallback(async () => {
    if (getTokens("user")) { setAnon(true); setAnonId(getAnonId()); return; }
    inflightAnon ??= identity.anon().finally(() => { inflightAnon = null; });
    const s = await inflightAnon;
    setAnonId(s.anon_id);
    setAnon(true);
  }, []);

  useEffect(() => {
    let live = true;
    ensureAnon().catch(() => { /* offline: surfaced by later calls */ }).finally(() => { if (live) setReady(true); });
    return () => { live = false; };
  }, [ensureAnon]);

  useEffect(() => onAuthExpired((kind) => {
    if (kind === "admin") { writeRole(null); setIsAdmin(false); setRole(null); return; }
    setAnon(false);
    ensureAnon().catch(() => { /* offline: retried on next ensureAnon */ });
  }), [ensureAnon]);

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
