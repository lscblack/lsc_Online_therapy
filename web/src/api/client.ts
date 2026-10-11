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

function refreshTokens(kind: TokenKind): Promise<boolean> {
  const inflight = refreshing[kind];
  if (inflight) return inflight;
  const p = (async () => {
    const cur = getTokens(kind);
    if (!cur) return false;
    try {
      const res = await rawFetch("/v1/identity/refresh", { method: "POST", body: { refresh_token: cur.refresh_token } }, null);
      if (!res.ok) return false;
      setTokens(kind, (await res.json()) as TokenPair);
      return true;
    } catch { return false; }
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
  return (text ? JSON.parse(text) : undefined) as T;
}
