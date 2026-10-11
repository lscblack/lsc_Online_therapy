import { ApiError, apiFetch, refreshTokens } from "./client";
import { getTokens, setAnonId, setTokens } from "../auth/tokenStore";
import type { AnonSession, TokenPair, UpgradeResponse } from "./types";

export const identity = {
  /** Create an anonymous identity and store the end-user token pair. */
  async anon(): Promise<AnonSession> {
    const s = await apiFetch<AnonSession>("/v1/identity/anon", { method: "POST", auth: "none" });
    setTokens("user", s);
    setAnonId(s.anon_id);
    return s;
  },
  upgrade: (passphrase: string) =>
    apiFetch<UpgradeResponse>("/v1/identity/upgrade", { method: "POST", body: { passphrase } }),
  async recover(anon_id: string, passphrase: string): Promise<AnonSession> {
    const s = await apiFetch<AnonSession>("/v1/identity/recover", { method: "POST", auth: "none", body: { anon_id, passphrase } });
    setTokens("user", s);
    setAnonId(s.anon_id);
    return s;
  },
  /** Explicit refresh of the end-user pair (same shared path as the 401 retry). */
  async refresh(): Promise<TokenPair> {
    if (!(await refreshTokens("user"))) throw new ApiError("auth_expired", "Session expired", 401);
    const t = getTokens("user");
    if (!t) throw new ApiError("auth_expired", "Session expired", 401);
    return t;
  },
};
