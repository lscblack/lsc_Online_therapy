import { useMemo, useState } from "react";
import { admin } from "../../api/admin";
import type { Document } from "../../api/types";
import { useAuth } from "../../auth/useAuth";
import { useT, type TKey } from "../../i18n/useT";
import { Donut } from "./charts";
import ConfirmDialog from "./ConfirmDialog";
import DocumentDetail from "./DocumentDetail";
import UploadDialog from "./UploadDialog";
import { useAdminList } from "./useAdminList";

const STATUS: Record<Document["status"], TKey> = {
  uploaded: "adminStatusUploaded", processing: "adminStatusProcessing", indexed: "adminStatusIndexed", failed: "adminStatusFailed",
};
const REVIEW: Record<Document["review_status"], TKey> = {
  pending: "adminReviewPending", approved: "adminReviewApproved", rejected: "adminReviewRejected",
};
type Filter = "all" | "pending" | "approved" | "rejected";
const load = () => admin.listDocuments();

export default function Documents({ canDelete }: { canDelete: boolean }) {
  const { t } = useT();
  const { adminLogout } = useAuth();
  const { items, loading, err, refresh, run, fail } = useAdminList<Document>(load);
  const [uploading, setUploading] = useState(false);
  const [deleting, setDeleting] = useState<Document | null>(null);
  const [viewing, setViewing] = useState<Document | null>(null);
  const [filter, setFilter] = useState<Filter>("all");
  const [query, setQuery] = useState("");

  const total = items.length;
  const indexed = items.filter((d) => d.status === "indexed").length;
  const pending = items.filter((d) => d.review_status === "pending").length;
  const approved = items.filter((d) => d.review_status === "approved").length;

  const shown = useMemo(() => {
    const q = query.trim().toLowerCase();
    return items.filter((d) =>
      (filter === "all" || d.review_status === filter) &&
      (!q || d.title.toLowerCase().includes(q) || (d.topic_tags || []).some((x) => x.toLowerCase().includes(q))));
  }, [items, filter, query]);

  const stats = [
    { label: t("ovDocuments"), value: total, pct: total ? Math.round((indexed / total) * 100) : 0 },
    { label: t("adminReviewApproved"), value: approved, pct: total ? Math.round((approved / total) * 100) : 0 },
    { label: t("ovPending"), value: pending, pct: total ? Math.round((pending / total) * 100) : 0 },
    { label: t("adminStatusIndexed"), value: indexed, pct: total ? Math.round((indexed / total) * 100) : 0 },
  ];
  const filters: [Filter, string][] = [
    ["all", t("docAll")], ["pending", t("adminReviewPending")],
    ["approved", t("adminReviewApproved")], ["rejected", t("adminReviewRejected")],
  ];

  return (
    <div className="stack">
      {/* Stat cards */}
      <div className="dash-stats">
        {stats.map((s, i) => (
          <div key={i} className="card dash-stat" style={{ cursor: "default" }}>
            <div className="dash-stat-top">
              <div>
                <div className="dash-stat-value">{s.value}</div>
                <div className="dash-stat-label">{s.label}</div>
              </div>
              <div className="dash-stat-donut"><Donut value={s.pct} size={60} /></div>
            </div>
          </div>
        ))}
      </div>

      <section className="panel" aria-label={t("adminDocuments")}>
        <div className="panel-head">
          <div className="doc-filters">
            {filters.map(([k, label]) => (
              <button key={k} type="button" className={`chip${filter === k ? " chip-on" : ""}`} onClick={() => setFilter(k)}>{label}</button>
            ))}
          </div>
          <div className="panel-actions">
            <input className="doc-search" type="search" value={query} onChange={(e) => setQuery(e.target.value)}
              placeholder={t("docSearch")} aria-label={t("docSearch")} />
            <button type="button" className="btn btn-primary btn-sm" onClick={() => setUploading(true)}>{t("adminUpload")}</button>
            <button type="button" className="btn btn-sm" onClick={() => void refresh()}>{t("adminRefresh")}</button>
          </div>
        </div>

        {err && <p role="alert" className="admin-error">{err}</p>}
        {loading && <p className="muted">{t("adminLoading")}</p>}
        {!loading && !err && shown.length === 0 && <p className="muted">{t("adminEmpty")}</p>}

        {shown.length > 0 && (
          <div className="table-wrap">
            <table className="admin-table doc-table">
              <thead><tr>
                <th scope="col">{t("adminColTitle")}</th>
                <th scope="col">{t("adminLanguage2")}</th>
                <th scope="col">{t("adminColStatus")}</th>
                <th scope="col">{t("adminColReview")}</th>
                <th scope="col">{t("dvCreated")}</th>
                <th scope="col">{t("adminColActions")}</th>
              </tr></thead>
              <tbody>
                {shown.map((d) => (
                  <tr key={d.id}>
                    <td>
                      <button type="button" className="doc-title-link" onClick={() => setViewing(d)}>{d.title}</button>
                      <div className="doc-sub muted">{d.source_filename ?? ""}{d.topic_tags.length ? ` · ${d.topic_tags.join(", ")}` : ""}</div>
                    </td>
                    <td>{d.language ? <span className="badge">{d.language}</span> : <span className="muted">—</span>}</td>
                    <td><span className={`badge badge-${d.status}`}>{t(STATUS[d.status] ?? "adminStatusUploaded")}</span></td>
                    <td><span className={`badge badge-${d.review_status}`}>{t(REVIEW[d.review_status] ?? "adminReviewPending")}</span></td>
                    <td className="doc-date">{new Date(d.created_at).toLocaleDateString()}</td>
                    <td className="admin-actions">
                      <button type="button" className="btn btn-sm" aria-label={`${t("dvView")}: ${d.title}`} onClick={() => setViewing(d)}>{t("dvView")}</button>
                      <button type="button" className="btn btn-sm" aria-label={`${t("adminApprove")}: ${d.title}`} onClick={() => void run(() => admin.reviewDocument(d.id, "approved", undefined))}>{t("adminApprove")}</button>
                      <button type="button" className="btn btn-sm" aria-label={`${t("adminReject")}: ${d.title}`} onClick={() => void run(() => admin.reviewDocument(d.id, "rejected", undefined))}>{t("adminReject")}</button>
                      <button type="button" className="btn btn-sm" aria-label={`${t("adminReindex")}: ${d.title}`} onClick={() => void run(() => admin.reindexDocument(d.id))}>{t("adminReindex")}</button>
                      {canDelete && <button type="button" className="btn btn-sm btn-danger" aria-label={`${t("adminDelete")}: ${d.title}`} onClick={() => setDeleting(d)}>{t("adminDelete")}</button>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {uploading && (
        <UploadDialog
          onClose={() => setUploading(false)}
          onDone={() => { setUploading(false); void refresh(); }}
          onAuthFail={(e) => { fail(e); if ((e as { status?: number })?.status === 401) adminLogout(); }}
        />
      )}
      {viewing && (
        <DocumentDetail doc={viewing} canReview onClose={() => setViewing(null)} onAction={(fn) => void run(fn)} />
      )}
      {deleting && (
        <ConfirmDialog
          message={`${t("adminConfirmDelete")} (${deleting.title})`}
          onCancel={() => setDeleting(null)}
          onConfirm={() => { const id = deleting.id; setDeleting(null); void run(() => admin.deleteDocument(id)); }}
        />
      )}
    </div>
  );
}
