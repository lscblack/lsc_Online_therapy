import { useCallback, useEffect, useState } from "react";
import { admin } from "../../api/admin";
import type { AuditEntry, Document, ModelConfig, SystemInfo, User } from "../../api/types";
import { useAuth } from "../../auth/useAuth";
import { useT } from "../../i18n/useT";
import { adminErrorKey, isUnauthorized } from "./adminErrors";
import { AreaChart, Donut } from "./charts";

type Section = "overview" | "docs" | "users" | "audit" | "models";

/** Monthly cumulative document counts (last 6 months) from created_at, for the trend chart. */
function monthlySeries(docs: Document[]): { data: number[]; labels: string[] } {
  const now = new Date();
  const months: { key: string; label: string }[] = [];
  for (let i = 5; i >= 0; i--) {
    const d = new Date(now.getFullYear(), now.getMonth() - i, 1);
    months.push({ key: `${d.getFullYear()}-${d.getMonth()}`, label: d.toLocaleString(undefined, { month: "short" }) });
  }
  const perMonth = new Map(months.map((m) => [m.key, 0]));
  for (const doc of docs) {
    const d = new Date(doc.created_at);
    const k = `${d.getFullYear()}-${d.getMonth()}`;
    if (perMonth.has(k)) perMonth.set(k, (perMonth.get(k) ?? 0) + 1);
  }
  let cum = Math.max(0, docs.length - months.reduce((a, m) => a + (perMonth.get(m.key) ?? 0), 0));
  const data = months.map((m) => (cum += perMonth.get(m.key) ?? 0));
  return { data, labels: months.map((m) => m.label) };
}

export default function Overview({ onGo }: { onGo: (s: Section) => void }) {
  const { t } = useT();
  const { role, adminLogout } = useAuth();
  const [docs, setDocs] = useState<Document[] | null>(null);
  const [users, setUsers] = useState<User[] | null>(null);
  const [models, setModels] = useState<ModelConfig | null>(null);
  const [audit, setAudit] = useState<AuditEntry[] | null>(null);
  const [sys, setSys] = useState<SystemInfo | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const loadAll = useCallback(async () => {
    try {
      const [d, u, m, a, sy] = await Promise.all([
        admin.listDocuments(), admin.listUsers(), admin.getModels(), admin.listAudit(), admin.getSystem(),
      ]);
      setDocs(d); setUsers(u); setModels(m); setAudit(a); setSys(sy); setErr(null);
    } catch (e) {
      setErr(t(adminErrorKey(e)));
      if (isUnauthorized(e)) adminLogout();
    }
  }, [t, adminLogout]);

  useEffect(() => { void loadAll(); }, [loadAll]);

  const total = docs?.length ?? 0;
  const indexed = docs?.filter((d) => d.status === "indexed").length ?? 0;
  const pending = docs?.filter((d) => d.review_status === "pending").length ?? 0;
  const approved = docs?.filter((d) => d.review_status === "approved").length ?? 0;
  const indexedPct = total ? Math.round((indexed / total) * 100) : 0;
  const approvedPct = total ? Math.round((approved / total) * 100) : 0;
  const series = monthlySeries(docs ?? []);

  const cards = [
    { k: "docs" as Section, value: total, label: t("ovDocuments"), sub: `${indexed} ${t("ovIndexed")}`, pct: indexedPct },
    { k: "docs" as Section, value: pending, label: t("ovPending"), sub: t("ovNeedsReview"), pct: total ? Math.round((pending / total) * 100) : 0 },
    { k: "users" as Section, value: users?.length ?? 0, label: t("ovUsers"), sub: t("ovRegistered"), pct: null },
  ];

  return (
    <div className="stack">
      {err && <p className="admin-error">{err}</p>}

      {/* Welcome banner */}
      <div className="dash-banner">
        <div>
          <div className="dash-banner-eyebrow">{t("adminConsole")}</div>
          <h3 className="dash-banner-title">{t("ovWelcome")}</h3>
          <p className="dash-banner-sub">{t("ovWelcomeSub")}</p>
          <div className="dash-banner-actions">
            <button type="button" className="btn lx-cta-btn" onClick={() => onGo("docs")}>{t("adminUpload")}</button>
            <button type="button" className="btn btn-ghost dash-banner-ghost" onClick={() => onGo("models")}>{t("adminModels")}</button>
          </div>
        </div>
        <div className="dash-banner-badge"><Donut value={indexedPct} size={120} label={t("ovIndexed")} /></div>
      </div>

      {/* Stat cards */}
      <div className="dash-stats">
        {cards.map((c, i) => (
          <button key={i} type="button" className="card dash-stat" onClick={() => onGo(c.k)}>
            <div className="dash-stat-top">
              <div>
                <div className="dash-stat-value">{c.value}</div>
                <div className="dash-stat-label">{c.label}</div>
              </div>
              {c.pct !== null && <div className="dash-stat-donut"><Donut value={c.pct} size={64} /></div>}
            </div>
            <div className="muted dash-stat-sub">{c.sub}</div>
          </button>
        ))}
        <div className="card dash-stat dash-stat-model">
          <div className="dash-stat-label">{t("ovActiveModel")}</div>
          <div className="dash-stat-model-id">{models ? `${models.active_provider} · ${models.active_model}` : "—"}</div>
          <span className="badge badge-green">{t("ovOperational")}</span>
        </div>
        <div className="card dash-stat dash-stat-model">
          <div className="dash-stat-label">{t("ovSpeech")}</div>
          <div className="dash-stat-model-id">
            {sys ? `${sys.stt_provider === "whisper_local" ? `Whisper (${sys.whisper_model})` : sys.stt_provider}` : "—"}
          </div>
          {sys && (sys.stt_device === "cuda"
            ? <span className="badge badge-green">{t("ovGpu")} ✓</span>
            : sys.stt_device === "cpu"
              ? <span className="badge badge-warn">{t("ovCpu")}</span>
              : <span className="badge">{sys.stt_device}</span>)}
        </div>
      </div>

      {/* Trend + review breakdown */}
      <div className="dash-row">
        <div className="card dash-chart">
          <div className="dash-chart-head">
            <h3>{t("ovKnowledgeGrowth")}</h3>
            <span className="badge badge-green">+{series.data[series.data.length - 1] - series.data[0]} / 6{t("ovMonthsShort")}</span>
          </div>
          <div className="dash-chart-body"><AreaChart data={series.data} labels={series.labels} /></div>
        </div>
        <div className="card dash-breakdown">
          <h3>{t("ovReviewStatus")}</h3>
          <ul className="dash-legend">
            <li><span className="dot dot-ok" /> {t("adminReviewApproved")} <b>{approved}</b></li>
            <li><span className="dot dot-warn" /> {t("adminReviewPending")} <b>{pending}</b></li>
            <li><span className="dot dot-bad" /> {t("adminReviewRejected")} <b>{(docs?.filter((d) => d.review_status === "rejected").length) ?? 0}</b></li>
          </ul>
          <div className="dash-breakdown-donut"><Donut value={approvedPct} size={120} label={t("adminReviewApproved")} /></div>
        </div>
      </div>

      {/* Recent activity */}
      {role === "admin" && (
        <div className="card">
          <div className="dash-chart-head"><h3>{t("ovRecentActivity")}</h3>
            <button type="button" className="btn btn-sm" onClick={() => onGo("audit")}>{t("ovViewAll")}</button></div>
          <ul className="dash-activity">
            {(audit ?? []).slice(0, 6).map((a) => (
              <li key={a.id}>
                <span className="dash-act-action">{a.action}</span>
                <span className="muted dash-act-target">{a.target ?? ""}</span>
                <span className="muted dash-act-time">{new Date(a.at).toLocaleString()}</span>
              </li>
            ))}
            {(!audit || audit.length === 0) && <li className="muted">{t("adminEmpty")}</li>}
          </ul>
        </div>
      )}
    </div>
  );
}
