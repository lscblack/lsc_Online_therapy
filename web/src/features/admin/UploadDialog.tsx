import { useRef, useState, type DragEvent, type FormEvent } from "react";
import Modal from "../../components/Modal";
import { admin } from "../../api/admin";
import { useT } from "../../i18n/useT";
import { adminErrorKey } from "./adminErrors";

function fmtSize(n: number): string {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(0)} KB`;
  return `${(n / 1024 / 1024).toFixed(1)} MB`;
}

export default function UploadDialog({ onClose, onDone, onAuthFail }: { onClose: () => void; onDone: () => void; onAuthFail: (e: unknown) => void }) {
  const { t } = useT();
  const [title, setTitle] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [language, setLanguage] = useState("");
  const [tags, setTags] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [dragging, setDragging] = useState(false);
  const inputRef = useRef<HTMLInputElement | null>(null);

  const pick = (f: File | null | undefined) => {
    if (!f) return;
    setFile(f);
    if (!title.trim()) setTitle(f.name.replace(/\.[^.]+$/, "")); // sensible default title
  };
  const onDrop = (e: DragEvent) => {
    e.preventDefault(); setDragging(false);
    pick(e.dataTransfer.files?.[0]);
  };

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (!file || !title.trim()) return;
    const form = new FormData();
    form.append("title", title.trim());
    form.append("file", file);
    if (language.trim()) form.append("language", language.trim());
    const list = tags.split(",").map((s) => s.trim()).filter(Boolean);
    if (list.length) form.append("topic_tags", list.join(","));
    setBusy(true); setErr(null);
    try { await admin.uploadDocument(form); onDone(); }
    catch (x) { setErr(t(adminErrorKey(x))); onAuthFail(x); }
    finally { setBusy(false); }
  }

  return (
    <Modal title={t("adminUpload")} onClose={onClose}>
      <form onSubmit={submit}>
        {/* Drag & drop zone */}
        <div
          className={`dropzone${dragging ? " is-drag" : ""}${file ? " has-file" : ""}`}
          onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
          onDragLeave={() => setDragging(false)}
          onDrop={onDrop}
          onClick={() => inputRef.current?.click()}
          role="button" tabIndex={0}
          aria-label={t("upDrop")}
          onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") inputRef.current?.click(); }}
        >
          <input ref={inputRef} type="file" accept="application/pdf,.pdf,.txt" hidden
            aria-label={t("adminFile")} onChange={(e) => pick(e.target.files?.[0])} />
          <svg viewBox="0 0 24 24" width="40" height="40" aria-hidden="true" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
            <path d="M12 16V6M8 10l4-4 4 4" /><path d="M4 16v2a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-2" />
          </svg>
          {file ? (
            <div className="dropzone-file">
              <strong>{file.name}</strong>
              <span className="muted">{fmtSize(file.size)} · {t("upChange")}</span>
            </div>
          ) : (
            <div className="dropzone-hint">
              <strong>{t("upDrop")}</strong>
              <span className="muted">{t("upBrowse")}</span>
            </div>
          )}
        </div>

        <label className="field">{t("adminDocTitle")}
          <input required value={title} onChange={(e) => setTitle(e.target.value)} />
        </label>
        <div className="up-row">
          <label className="field">{t("adminLanguage")}
            <input value={language} onChange={(e) => setLanguage(e.target.value)} placeholder="en / rw" />
          </label>
          <label className="field">{t("adminTags")}
            <input value={tags} onChange={(e) => setTags(e.target.value)} />
          </label>
        </div>
        {err && <p role="alert" className="admin-error">{err}</p>}
        <div className="modal-actions">
          <button type="button" className="btn" onClick={onClose}>{t("adminCancel")}</button>
          <button type="submit" className="btn btn-primary" disabled={busy || !file || !title.trim()}>
            {busy ? t("obSaving") : t("adminUploadSubmit")}
          </button>
        </div>
      </form>
    </Modal>
  );
}
