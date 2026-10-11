import { API_BASE } from "../config";
import { clearTokens, getTokens, setTokens, type TokenKind } from "../auth/tokenStore";
import type { ErrorEnvelope, TokenPair } from "./types";

export class ApiError extends Error {
  readonly code: string;
  readonly status: number;
  readonly details?: unknown;
  constructor(code: string, message: string, status: number, details?: unknown) {
    super(message);
    this.name = "ApiError";
    this.code = code;
    this.status = status;
    this.details = details;
  }
}

export type AuthMode = TokenKind | "none";
export interface ApiOptions {
  method?: string;
  /** Plain objects are sent as JSON; FormData/Blob are sent as-is. */
  body?: unknown;
  /** Which token to attach: "user" (default), "admin", or "none". */
  auth?: AuthMode;
  signal?: AbortSignal;
  headers?: Record<string, string>;
}

const refreshing: Partial<Record<TokenKind, Promise<boolean>>> = {};

type ExpiredListener = (kind: TokenKind) => void;
const expiredListeners = new Set<ExpiredListener>();
/** Subscribe to definitive session expiry (tokens cleared after refresh was rejected). */
export function onAuthExpired(cb: ExpiredListener): () => void {
  expiredListeners.add(cb);
  return () => { expiredListeners.delete(cb); };
}

function isTokenPair(v: unknown): v is TokenPair {
  const t = v as Partial<TokenPair> | null;
  return !!t && typeof t.access_token === "string" && t.access_token !== "" &&
    typeof t.refresh_token === "string" && t.refresh_token !== "";
}

async function readError(res: Response): Promise<ApiError> {
  try {
    const j = (await res.json()) as Partial<ErrorEnvelope>;
    if (j && j.error && typeof j.error.code === "string") {
      return new ApiError(j.error.code, j.error.message ?? res.statusText, res.status, j.error.details);
    }
  } catch { /* not JSON */ }
  return new ApiError("error", res.statusText || "Request failed", res.status);
}

async function rawFetch(path: string, o: ApiOptions, token: string | null): Promise<Response> {
  const headers: Record<string, string> = { Accept: "application/json", ...o.headers };
  let body: BodyInit | undefined;
  if (o.body instanceof FormData || o.body instanceof Blob) body = o.body;
  else if (o.body !== undefined) { headers["Content-Type"] = "application/json"; body = JSON.stringify(o.body); }
  if (token) headers.Authorization = `Bearer ${token}`;
  try {
    return await fetch(`${API_BASE}${path}`, { method: o.method ?? "GET", headers, body, signal: o.signal });
  } catch (e) {
    if (e instanceof DOMException && e.name === "AbortError") throw e;
    throw new ApiError("offline", "Network unreachable", 0);
  }
}

/**
 * Shared single-flight refresh. Resolves true when new tokens were stored, false when the
 * server DEFINITIVELY rejected the refresh token (400/401/403). Throws ApiError (offline, 5xx,
 * malformed body) on transient failures, leaving stored tokens untouched.
 */
export function refreshTokens(kind: TokenKind): Promise<boolean> {
  const inflight = refreshing[kind];
  if (inflight) return inflight;
  const p = (async () => {
    const cur = getTokens(kind);
    if (!cur) return false;
    const res = await rawFetch("/v1/identity/refresh", { method: "POST", body: { refresh_token: cur.refresh_token } }, null);
    if (res.status === 400 || res.status === 401 || res.status === 403) return false;
    if (!res.ok) throw await readError(res);
    let data: unknown;
    try { data = await res.json(); } catch { data = null; }
    if (!isTokenPair(data)) throw new ApiError("bad_response", "Malformed refresh response", res.status);
    setTokens(kind, data);
    return true;
  })().finally(() => { delete refreshing[kind]; });
  refreshing[kind] = p;
  return p;
}

/** Fetch with auth + one refresh-on-401 retry; returns the raw OK Response or throws ApiError. */
export async function apiFetchRaw(path: string, o: ApiOptions = {}): Promise<Response> {
  const mode = o.auth ?? "user";
  let res = await rawFetch(path, o, mode === "none" ? null : getTokens(mode)?.access_token ?? null);
  if (res.status === 401 && mode !== "none" && getTokens(mode)) {
    if (await refreshTokens(mode)) {
      res = await rawFetch(path, o, getTokens(mode)?.access_token ?? null);
    } else {
      clearTokens(mode);
      expiredListeners.forEach((cb) => cb(mode));
      throw new ApiError("auth_expired", "Session expired", 401);
    }
  }
  if (!res.ok) throw await readError(res);
  return res;
}

export async function apiFetch<T>(path: string, o: ApiOptions = {}): Promise<T> {
  const res = await apiFetchRaw(path, o);
  if (res.status === 204) return undefined as T;
  const text = await res.text();
  if (!text) return undefined as T;
  try { return JSON.parse(text) as T; }
  catch { throw new ApiError("bad_response", "Server returned a non-JSON response", res.status); }
}
