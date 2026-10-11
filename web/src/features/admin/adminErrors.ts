import { ApiError } from "../../api/client";
import type { TKey } from "../../i18n/useT";

/** Map an admin API failure to a user-facing i18n key. Never exposes tokens or raw bodies. */
export function adminErrorKey(e: unknown, ctx: "login" | "action" = "action"): TKey {
  if (e instanceof ApiError) {
    if (e.status === 503) return "adminUnavailable";
    if (e.status === 401) return ctx === "login" ? "adminInvalidCreds" : "adminSessionExpired";
    if (e.status === 403) return "adminForbidden";
  }
  return "adminGenericError";
}
export function isUnauthorized(e: unknown): boolean {
  return e instanceof ApiError && e.status === 401;
}
