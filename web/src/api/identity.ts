import { apiFetch } from "./client";
import { getTokens, setTokens } from "../auth/tokenStore";
import type { AnonSession, TokenPair, UpgradeResponse } from "./types";

export const identity = {
  /** Create an anonymous identity and store the end-user token pair. */
  async anon(): Promise<AnonSession> {
    const s = await apiFetch<AnonSession>("/v1/identity/anon", { method: "POST", auth: "none" });
    setTokens("user", s);
    return s;
  },
  upgrade: (passphrase: string) =>
    apiFetch<UpgradeResponse>("/v1/identity/upgrade", { method: "POST", body: { passphrase } }),
  async recover(anon_id: string, passphrase: string): Promise<AnonSession> {
    const s = await apiFetch<AnonSession>("/v1/identity/recover", { method: "POST", auth: "none", body: { anon_id, passphrase } });
    setTokens("user", s);
    return s;
  },
  /** Explicit refresh of the end-user pair. */
  async refresh(): Promise<TokenPair> {
    const cur = getTokens("user");
    const t = await apiFetch<TokenPair>("/v1/identity/refresh", { method: "POST", auth: "none", body: { refresh_token: cur?.refresh_token ?? "" } });
    setTokens("user", t);
    return t;
  },
};
