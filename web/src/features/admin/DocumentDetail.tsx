import { useEffect, useState } from "react";
import Modal from "../../components/Modal";
import { admin } from "../../api/admin";
import type { Chunk, Document } from "../../api/types";
import { useT, type TKey } from "../../i18n/useT";
import { adminErrorKey } from "./adminErrors";

const STATUS: Record<Document["status"], TKey> = {
  uploaded: "adminStatusUploaded", processing: "adminStatusProcessing", indexed: "adminStatusIndexed", failed: "adminStatusFailed",
};
const REVIEW: Record<Document["review_status"], TKey> = {
  pending: "adminReviewPending", approved: "adminReviewApproved", rejected: "adminReviewRejected",
};

/** Read-only overview of a document: metadata + the extracted text chunks the assistant retrieves,
 *  with the same review/reindex actions as the table row. */
export default function DocumentDetail({ doc, canReview, onClose, onAction }: {
  doc: Document; canReview: boolean; onClose: () => void;
  onAction: (fn: () => Promise<unknown>) => void;
}) {
  const { t } = useT();
  const [chunks, setChunks] = useState<Chunk[] | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    let live = true;
    admin.documentChunks(doc.id)
      .then((c) => { if (live) setChunks(c); })
      .catch((e) => { if (live) setErr(t(adminErrorKey(e))); });
    return () => { live = false; };
  }, [doc.id, t]);

  const act = (fn: () => Promise<unknown>) => { onAction(fn); onClose(); };

  return (
    <Modal title={doc.title} onClose={onClose}>
      <div className="docview">
        <div className="docview-meta">
          <span className={`badge badge-${doc.status}`}>{t(STATUS[doc.status])}</span>
          <span className={`badge badge-${doc.review_status}`}>{t(REVIEW[doc.review_status])}</span>
          {doc.language && <span className="badge">{doc.language}</span>}
          {doc.topic_tags.map((tag) => <span key={tag} className="badge">{tag}</span>)}
        </div>
        <dl className="docview-props">
          <div><dt>{t("dvFile")}</dt><dd>{doc.source_filename ?? "—"}</dd></div>
          <div><dt>{t("dvVersion")}</dt><dd>{doc.version}</dd></div>
          <div><dt>{t("dvCreated")}</dt><dd>{new Date(doc.created_at).toLocaleString()}</dd></div>
          <div><dt>{t("dvIndexed")}</dt><dd>{doc.indexed_at ? new Date(doc.indexed_at).toLocaleString() : "—"}</dd></div>
        </dl>
        {doc.review_notes && <p className="docview-notes"><strong>{t("dvNotes")}:</strong> {doc.review_notes}</p>}

        <h4 className="docview-h">{t("dvContent")} {chunks && <span className="muted">({chunks.length})</span>}</h4>
        {err && <p className="admin-error">{err}</p>}
        {!chunks && !err && <p className="muted">{t("adminLoading")}</p>}
        {chunks && chunks.length === 0 && <p className="muted">{t("dvNoContent")}</p>}
        <div className="docview-chunks">
          {(chunks ?? []).map((c) => (
            <div key={c.chunk_index} className="docview-chunk">
              <div className="docview-chunk-h muted">#{c.chunk_index + 1} · {c.token_count} {t("dvTokens")}</div>
              <p>{c.content}</p>
            </div>
          ))}
        </div>

        <div className="modal-actions">
          <button type="button" className="btn" onClick={onClose}>{t("adminCancel")}</button>
          {canReview && <>
            <button type="button" className="btn" onClick={() => act(() => admin.reindexDocument(doc.id))}>{t("adminReindex")}</button>
            <button type="button" className="btn btn-danger" onClick={() => act(() => admin.reviewDocument(doc.id, "rejected", undefined))}>{t("adminReject")}</button>
            <button type="button" className="btn btn-primary" onClick={() => act(() => admin.reviewDocument(doc.id, "approved", undefined))}>{t("adminApprove")}</button>
          </>}
        </div>
      </div>
    </Modal>
  );
}
