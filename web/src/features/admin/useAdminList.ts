import { useCallback, useEffect, useState } from "react";
import { useAuth } from "../../auth/useAuth";
import { useT } from "../../i18n/useT";
import { adminErrorKey, isUnauthorized } from "./adminErrors";

/** Load a list, expose a refresh, and a guarded `run` for mutations. 401 logs out (re-login). */
export function useAdminList<T>(load: () => Promise<T[]>) {
  const { t } = useT();
  const { adminLogout } = useAuth();
  const [items, setItems] = useState<T[]>([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);

  const fail = useCallback((e: unknown) => {
    setErr(t(adminErrorKey(e)));
    if (isUnauthorized(e)) adminLogout();
  }, [t, adminLogout]);

  const refresh = useCallback(async () => {
    setLoading(true);
    try { setItems(await load()); setErr(null); }
    catch (e) { fail(e); }
    finally { setLoading(false); }
  }, [load, fail]);

  useEffect(() => { void refresh(); }, [refresh]);

  const run = useCallback(async (fn: () => Promise<unknown>) => {
    try { await fn(); setErr(null); await refresh(); }
    catch (e) { fail(e); }
  }, [refresh, fail]);

  return { items, loading, err, refresh, run, fail };
}
