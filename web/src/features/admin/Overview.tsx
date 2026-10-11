import { useCallback, useEffect, useState } from "react";
import { admin } from "../../api/admin";
import type { Document, ModelConfig, User } from "../../api/types";
import { useAuth } from "../../auth/useAuth";
import { useT } from "../../i18n/useT";
import { adminErrorKey, isUnauthorized } from "./adminErrors";

type Section = "overview" | "docs" | "users" | "audit" | "models";

/** Dashboard overview: headline stats + quick links into each section. */
export default function Overview({ onGo }: { onGo: (s: Section) => void }) {
  const { t } = useT();
  const { adminLogout } = useAuth();
  const [docs, setDocs] = useState<Document[] | null>(null);
  const [users, setUsers] = useState<User[] | null>(null);
  const [models, setModels] = useState<ModelConfig | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const loadAll = useCallback(async () => {
    try {
      const [d, u, m] = await Promise.all([admin.listDocuments(), admin.listUsers(), admin.getModels()]);
      setDocs(d); setUsers(u); setModels(m); setErr(null);
    } catch (e) {
      setErr(t(adminErrorKey(e)));
      if (isUnauthorized(e)) adminLogout();
    }
  }, [t, adminLogout]);

  useEffect(() => { void loadAll(); }, [loadAll]);

  const pending = docs?.filter((d) => d.review_status === "pending").length ?? 0;
  const indexed = docs?.filter((d) => d.status === "indexed").length ?? 0;
  const stats = [
    { k: "docs" as Section, value: docs?.length ?? "—", label: t("ovDocuments"), sub: `${indexed} ${t("ovIndexed")}` },
    { k: "docs" as Section, value: pending, label: t("ovPending"), sub: t("ovNeedsReview") },
    { k: "users" as Section, value: users?.length ?? "—", label: t("ovUsers"), sub: t("ovRegistered") },
    { k: "models" as Section, value: models ? `${models.active_provider} · ${models.active_model}` : "—", label: t("ovActiveModel"), sub: models?.is_override ? t("mdlOverride") : t("mdlDefault"), wide: true },
  ];

  return (
    <div className="stack">
      {err && <p className="admin-error">{err}</p>}
      <div className="ov-grid">
        {stats.map((s, i) => (
          <button key={i} type="button" className={`card ov-card${s.wide ? " ov-card-wide" : ""}`} onClick={() => onGo(s.k)}>
            <div className="ov-value">{s.value}</div>
            <div className="ov-label">{s.label}</div>
            <div className="muted ov-sub">{s.sub}</div>
          </button>
        ))}
      </div>
      <div className="ov-links">
        <button type="button" className="btn" onClick={() => onGo("docs")}>{t("adminDocuments")}</button>
        <button type="button" className="btn" onClick={() => onGo("models")}>{t("adminModels")}</button>
        <button type="button" className="btn" onClick={() => onGo("audit")}>{t("adminAudit")}</button>
      </div>
    </div>
  );
}
