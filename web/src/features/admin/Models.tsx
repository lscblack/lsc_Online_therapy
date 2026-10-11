import { useCallback, useEffect, useState } from "react";
import { admin } from "../../api/admin";
import type { ModelConfig, ProviderInfo, TestModelResult } from "../../api/types";
import { useAuth } from "../../auth/useAuth";
import { useT } from "../../i18n/useT";
import { adminErrorKey, isUnauthorized } from "./adminErrors";

/** Admin-only: pick an AI provider + model for chat/voice, test any model live, and activate one. */
export default function Models() {
  const { t } = useT();
  const { adminLogout } = useAuth();
  const [cfg, setCfg] = useState<ModelConfig | null>(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);
  const [sel, setSel] = useState<string>("");            // selected provider name
  const [models, setModels] = useState<string[]>([]);     // live models for selected provider
  const [modelsLoading, setModelsLoading] = useState(false);
  const [custom, setCustom] = useState("");
  const [busy, setBusy] = useState<string | null>(null);  // "provider:model" being acted on
  const [results, setResults] = useState<Record<string, TestModelResult>>({});

  const fail = useCallback((e: unknown) => {
    setErr(t(adminErrorKey(e)));
    if (isUnauthorized(e)) adminLogout();
  }, [t, adminLogout]);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const c = await admin.getModels();
      setCfg(c); setErr(null);
      setSel((s) => s || c.active_provider);
    } catch (e) { fail(e); }
    finally { setLoading(false); }
  }, [fail]);

  useEffect(() => { void load(); }, [load]);

  // Load live models whenever the selected provider changes.
  useEffect(() => {
    if (!sel) return;
    let live = true;
    setModelsLoading(true);
    admin.providerModels(sel)
      .then((r) => { if (live) setModels(r.models); })
      .catch((e) => { if (live) fail(e); })
      .finally(() => { if (live) setModelsLoading(false); });
    return () => { live = false; };
  }, [sel, fail]);

  const key = (p: string, m: string) => `${p}:${m}`;

  const activate = async (provider: string, model: string) => {
    setBusy(key(provider, model));
    try { setCfg(await admin.setModel(provider, model)); setErr(null); }
    catch (e) { fail(e); }
    finally { setBusy(null); }
  };
  const test = async (provider: string, model: string) => {
    const k = key(provider, model);
    setBusy(k);
    try {
      const res = await admin.testModel(provider, model);
      setResults((m) => ({ ...m, [k]: res })); setErr(null);
    } catch (e) { fail(e); }
    finally { setBusy(null); }
  };

  if (loading) return <p className="muted">{t("adminLoading")}</p>;
  if (!cfg) return <p className="admin-error">{err ?? t("adminGenericError")}</p>;

  const provider: ProviderInfo | undefined = cfg.providers.find((p) => p.name === sel);
  const list = custom.trim() && !models.includes(custom.trim()) ? [custom.trim(), ...models] : models;

  return (
    <div className="stack">
      {err && <p className="admin-error">{err}</p>}

      <div className="card mdl-active">
        <div>
          <div className="muted mdl-active-label">{t("mdlActive")}</div>
          <div className="mdl-active-id">{cfg.active_provider} · {cfg.active_model}</div>
          <div className="mdl-active-meta">
            {cfg.is_override
              ? <span className="badge badge-green">{t("mdlOverride")}</span>
              : <span className="badge">{t("mdlDefault")}</span>}
          </div>
        </div>
      </div>

      {/* Provider picker */}
      <div className="mdl-providers">
        {cfg.providers.map((p) => (
          <button key={p.name} type="button" disabled={!p.enabled}
            className={`mdl-prov${sel === p.name ? " sel" : ""}${p.enabled ? "" : " off"}`}
            onClick={() => { setSel(p.name); setCustom(""); }}>
            <span className="mdl-prov-name">{p.label}</span>
            <span className={`badge ${p.tier === "local" ? "badge-green" : p.tier === "paid" ? "badge-warn" : ""}`}>{p.tier}</span>
            {!p.enabled && <span className="badge badge-danger">{t("mdlNoKey")}</span>}
          </button>
        ))}
      </div>

      {provider && (
        <div className="card">
          <p className="muted" style={{ marginTop: 0 }}>{provider.note}</p>
          <div className="mdl-add">
            <input value={custom} onChange={(e) => setCustom(e.target.value)}
              placeholder={t("mdlCustomPlaceholder")} aria-label={t("mdlCustomPlaceholder")} />
          </div>
          {modelsLoading && <p className="muted">{t("adminLoading")}</p>}
          <div className="mdl-grid">
            {list.map((m) => {
              const isActive = cfg.active_provider === provider.name && cfg.active_model === m;
              const k = key(provider.name, m);
              const r = results[k];
              return (
                <div key={m} className={`card mdl-card${isActive ? " mdl-card-active" : ""}`}>
                  <div className="mdl-card-head">
                    <code className="mdl-id">{m}</code>
                    {isActive && <span className="badge badge-green">{t("mdlActiveTag")}</span>}
                  </div>
                  {r && (
                    <div className={`mdl-result ${r.ok ? "ok" : "bad"}`}>
                      {r.ok
                        ? <><strong>{t("mdlOk")} · {r.latency_ms} ms</strong><p className="mdl-sample">{r.sample}</p></>
                        : <><strong>{t("mdlFailed")}</strong><p className="mdl-sample">{r.error}</p></>}
                    </div>
                  )}
                  <div className="mdl-actions">
                    <button type="button" className="btn btn-sm" disabled={busy === k} onClick={() => test(provider.name, m)}>
                      {busy === k ? t("mdlTesting") : t("mdlTest")}
                    </button>
                    <button type="button" className="btn btn-sm btn-primary" disabled={isActive || busy === k} onClick={() => activate(provider.name, m)}>
                      {isActive ? t("mdlActiveTag") : t("mdlActivate")}
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
