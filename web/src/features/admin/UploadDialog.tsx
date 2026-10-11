import { useState, type FormEvent } from "react";
import Modal from "../../components/Modal";
import { admin } from "../../api/admin";
import { useT } from "../../i18n/useT";
import { adminErrorKey } from "./adminErrors";

export default function UploadDialog({ onClose, onDone, onAuthFail }: { onClose: () => void; onDone: () => void; onAuthFail: (e: unknown) => void }) {
  const { t } = useT();
  const [title, setTitle] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [language, setLanguage] = useState("");
  const [tags, setTags] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

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
        <label className="field">{t("adminDocTitle")}
          <input required value={title} onChange={(e) => setTitle(e.target.value)} />
        </label>
        <label className="field">{t("adminFile")}
          <input type="file" aria-required="true" onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
        </label>
        <label className="field">{t("adminLanguage")}
          <input value={language} onChange={(e) => setLanguage(e.target.value)} />
        </label>
        <label className="field">{t("adminTags")}
          <input value={tags} onChange={(e) => setTags(e.target.value)} />
        </label>
        {err && <p role="alert" className="admin-error">{err}</p>}
        <div className="modal-actions">
          <button type="button" className="btn" onClick={onClose}>{t("adminCancel")}</button>
          <button type="submit" className="btn btn-primary" disabled={busy}>{t("adminUploadSubmit")}</button>
        </div>
      </form>
    </Modal>
  );
}
