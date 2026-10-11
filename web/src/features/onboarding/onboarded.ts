import { readStore, writeStore } from "../../storage";

export const ONBOARDED_KEY = "ubuzima.onboarded";
export const isOnboarded = (): boolean => readStore(ONBOARDED_KEY) === "1";
export const markOnboarded = (): void => writeStore(ONBOARDED_KEY, "1");
/** Re-entrancy: clears the flag so the wizard shows again (e.g. from settings). */
export function resetOnboarding(): void {
  try { localStorage.removeItem(ONBOARDED_KEY); } catch { /* storage unavailable */ }
}
