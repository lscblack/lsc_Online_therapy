import { useState } from "react";
import { admin } from "../../api/admin";
import type { Document } from "../../api/types";
import { useAuth } from "../../auth/useAuth";
import { useT, type TKey } from "../../i18n/useT";
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
const load = () => admin.listDocuments();

export default function Documents({ canDelete }: { canDelete: boolean }) {
  const { t } = useT();
  const { adminLogout } = useAuth();
  const { items, loading, err, refresh, run, fail } = useAdminList<Document>(load);
  const [uploading, setUploading] = useState(false);
  const [deleting, setDeleting] = useState<Document | null>(null);
  const [viewing, setViewing] = useState<Document | null>(null);

  return (
    <section className="panel" aria-label={t("adminDocuments")}>
      <div className="panel-head">
        <h3>{t("adminDocuments")}</h3>
        <div className="panel-actions">
          <button type="button" className="btn btn-primary btn-sm" onClick={() => setUploading(true)}>{t("adminUpload")}</button>
          <button type="button" className="btn btn-sm" onClick={() => void refresh()}>{t("adminRefresh")}</button>
        </div>
      </div>
      {err && <p role="alert" className="admin-error">{err}</p>}
      {loading && <p className="muted">{t("adminLoading")}</p>}
      {!loading && !err && items.length === 0 && <p className="muted">{t("adminEmpty")}</p>}
      {items.length > 0 && (
        <div className="table-wrap">
          <table className="admin-table">
            <thead><tr>
              <th scope="col">{t("adminColTitle")}</th><th scope="col">{t("adminColStatus")}</th>
              <th scope="col">{t("adminColReview")}</th><th scope="col">{t("adminColActions")}</th>
            </tr></thead>
            <tbody>
              {items.map((d) => (
                <tr key={d.id}>
                  <td>{d.title}</td>
                  <td><span className={`badge badge-${d.status}`}>{t(STATUS[d.status] ?? "adminStatusUploaded")}</span></td>
                  <td><span className={`badge badge-${d.review_status}`}>{t(REVIEW[d.review_status] ?? "adminReviewPending")}</span></td>
                  <td className="admin-actions">
                    <button type="button" className="btn" aria-label={`${t("dvView")}: ${d.title}`} onClick={() => setViewing(d)}>{t("dvView")}</button>
                    <button type="button" className="btn" aria-label={`${t("adminApprove")}: ${d.title}`} onClick={() => void run(() => admin.reviewDocument(d.id, "approved", undefined))}>{t("adminApprove")}</button>
                    <button type="button" className="btn" aria-label={`${t("adminReject")}: ${d.title}`} onClick={() => void run(() => admin.reviewDocument(d.id, "rejected", undefined))}>{t("adminReject")}</button>
                    <button type="button" className="btn" aria-label={`${t("adminReindex")}: ${d.title}`} onClick={() => void run(() => admin.reindexDocument(d.id))}>{t("adminReindex")}</button>
                    {canDelete && <button type="button" className="btn btn-danger" aria-label={`${t("adminDelete")}: ${d.title}`} onClick={() => setDeleting(d)}>{t("adminDelete")}</button>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {uploading && (
        <UploadDialog
          onClose={() => setUploading(false)}
          onDone={() => { setUploading(false); void refresh(); }}
          onAuthFail={(e) => { fail(e); if ((e as { status?: number })?.status === 401) adminLogout(); }}
        />
      )}
      {viewing && (
        <DocumentDetail doc={viewing} canReview onClose={() => setViewing(null)}
          onAction={(fn) => void run(fn)} />
      )}
      {deleting && (
        <ConfirmDialog
          message={`${t("adminConfirmDelete")} (${deleting.title})`}
          onCancel={() => setDeleting(null)}
          onConfirm={() => { const id = deleting.id; setDeleting(null); void run(() => admin.deleteDocument(id)); }}
        />
      )}
    </section>
  );
}
