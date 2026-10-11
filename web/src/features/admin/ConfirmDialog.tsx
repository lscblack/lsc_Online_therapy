import Modal from "../../components/Modal";
import { useT } from "../../i18n/useT";

export default function ConfirmDialog({ message, onConfirm, onCancel }: { message: string; onConfirm: () => void; onCancel: () => void }) {
  const { t } = useT();
  return (
    <Modal title={message} onClose={onCancel}>
      <div className="modal-actions">
        <button type="button" className="btn" onClick={onCancel}>{t("adminCancel")}</button>
        <button type="button" className="btn btn-danger" onClick={onConfirm}>{t("adminConfirm")}</button>
      </div>
    </Modal>
  );
}
