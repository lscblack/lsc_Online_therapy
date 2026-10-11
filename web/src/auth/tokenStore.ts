import type { TokenPair } from "../api/types";

export type TokenKind = "user" | "admin";
const KEYS: Record<TokenKind, string> = { user: "ubuzima.tokens.user", admin: "ubuzima.tokens.admin" };

export function getTokens(kind: TokenKind): TokenPair | null {
  try {
    const raw = localStorage.getItem(KEYS[kind]);
    if (!raw) return null;
    const p = JSON.parse(raw) as Partial<TokenPair>;
    return typeof p.access_token === "string" && typeof p.refresh_token === "string" ? (p as TokenPair) : null;
  } catch { return null; }
}
export function setTokens(kind: TokenKind, t: TokenPair): void {
  try {
    localStorage.setItem(KEYS[kind], JSON.stringify({ access_token: t.access_token, refresh_token: t.refresh_token, token_type: t.token_type }));
  } catch { /* storage unavailable */ }
}
export function clearTokens(kind: TokenKind): void {
  try { localStorage.removeItem(KEYS[kind]); } catch { /* storage unavailable */ }
}

const ANON_KEY = "ubuzima.anon_id";
export function getAnonId(): string | null {
  try { return localStorage.getItem(ANON_KEY); } catch { return null; }
}
export function setAnonId(id: string): void {
  try { localStorage.setItem(ANON_KEY, id); } catch { /* storage unavailable */ }
}
export function clearAnonId(): void {
  try { localStorage.removeItem(ANON_KEY); } catch { /* storage unavailable */ }
}
