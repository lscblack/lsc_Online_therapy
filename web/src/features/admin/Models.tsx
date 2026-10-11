import { useCallback, useEffect, useState } from "react";
import { admin } from "../../api/admin";
import type { ModelConfig, TestModelResult } from "../../api/types";
import { useAuth } from "../../auth/useAuth";
import { useT } from "../../i18n/useT";
import { adminErrorKey, isUnauthorized } from "./adminErrors";

/** Admin-only: view the active chat/voice model and switch between models, with a live probe. */
export default function Models() {
  const { t } = useT();
  const { adminLogout } = useAuth();
  const [cfg, setCfg] = useState<ModelConfig | null>(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);
  const [custom, setCustom] = useState("");
  const [busy, setBusy] = useState<string | null>(null); // model id being acted on
  const [results, setResults] = useState<Record<string, TestModelResult>>({});

  const fail = useCallback((e: unknown) => {
    setErr(t(adminErrorKey(e)));
    if (isUnauthorized(e)) adminLogout();
  }, [t, adminLogout]);

  const load = useCallback(async () => {
    setLoading(true);
    try { setCfg(await admin.getModels()); setErr(null); }
    catch (e) { fail(e); }
    finally { setLoading(false); }
  }, [fail]);

  useEffect(() => { void load(); }, [load]);

  const activate = async (model: string) => {
    setBusy(model);
    try { setCfg(await admin.setModel(model)); setErr(null); }
    catch (e) { fail(e); }
    finally { setBusy(null); }
  };

  const test = async (model: string) => {
    setBusy(model);
    try {
      const r = await admin.testModel(model);
      setResults((m) => ({ ...m, [model]: r }));
      setErr(null);
    } catch (e) { fail(e); }
    finally { setBusy(null); }
  };

  if (loading) return <p className="muted">{t("adminLoading")}</p>;
  if (!cfg) return <p className="admin-error">{err ?? t("adminGenericError")}</p>;

  const rows = [...cfg.catalog];
  if (custom.trim() && !rows.some((m) => m.id === custom.trim())) {
    rows.push({ id: custom.trim(), label: custom.trim(), tier: "custom", note: t("mdlCustomNote") });
  }

  return (
    <div className="stack">
      {err && <p className="admin-error">{err}</p>}

      <div className="card mdl-active">
        <div>
          <div className="muted mdl-active-label">{t("mdlActive")}</div>
          <div className="mdl-active-id">{cfg.active}</div>
          <div className="mdl-active-meta">
            {cfg.is_override
              ? <span className="badge badge-green">{t("mdlOverride")}</span>
              : <span className="badge">{t("mdlDefault")}</span>}
            <span className="badge">{cfg.provider}</span>
          </div>
        </div>
      </div>

      <div className="mdl-add">
        <input value={custom} onChange={(e) => setCustom(e.target.value)}
          placeholder={t("mdlCustomPlaceholder")} aria-label={t("mdlCustomPlaceholder")} />
      </div>

      <div className="mdl-grid">
        {rows.map((m) => {
          const isActive = m.id === cfg.active;
          const r = results[m.id];
          return (
            <div key={m.id} className={`card mdl-card${isActive ? " mdl-card-active" : ""}`}>
              <div className="mdl-card-head">
                <div>
                  <span className="mdl-name">{m.label}</span>
                  <span className={`badge ${m.tier === "free" ? "badge-green" : m.tier === "paid" ? "badge-warn" : ""}`}>{m.tier}</span>
                </div>
                {isActive && <span className="badge badge-green">{t("mdlActiveTag")}</span>}
              </div>
              <code className="mdl-id">{m.id}</code>
              <p className="muted mdl-note">{m.note}</p>
              {r && (
                <div className={`mdl-result ${r.ok ? "ok" : "bad"}`}>
                  {r.ok
                    ? <><strong>{t("mdlOk")} · {r.latency_ms} ms</strong><p className="mdl-sample">{r.sample}</p></>
                    : <><strong>{t("mdlFailed")}</strong><p className="mdl-sample">{r.error}</p></>}
                </div>
              )}
              <div className="mdl-actions">
                <button type="button" className="btn btn-sm" disabled={busy === m.id} onClick={() => test(m.id)}>
                  {busy === m.id ? t("mdlTesting") : t("mdlTest")}
                </button>
                <button type="button" className="btn btn-sm btn-primary" disabled={isActive || busy === m.id} onClick={() => activate(m.id)}>
                  {isActive ? t("mdlActiveTag") : t("mdlActivate")}
                </button>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
