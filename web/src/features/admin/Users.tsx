import { useState } from "react";
import { admin } from "../../api/admin";
import type { User } from "../../api/types";
import { useT } from "../../i18n/useT";
import ConfirmDialog from "./ConfirmDialog";
import { useAdminList } from "./useAdminList";

const load = () => admin.listUsers();

export default function Users() {
  const { t } = useT();
  const { items, loading, err, refresh, run } = useAdminList<User>(load);
  const [target, setTarget] = useState<User | null>(null);
  return (
    <section aria-label={t("adminUsers")}>
      <div className="admin-toolbar"><button type="button" className="btn" onClick={() => void refresh()}>{t("adminRefresh")}</button></div>
      {err && <p role="alert" className="admin-error">{err}</p>}
      {loading && <p className="lead">{t("adminLoading")}</p>}
      {!loading && !err && items.length === 0 && <p className="lead">{t("adminEmpty")}</p>}
      {items.length > 0 && (
        <div className="table-wrap">
          <table className="admin-table">
            <thead><tr>
              <th scope="col">{t("adminColEmail")}</th><th scope="col">{t("adminColRole")}</th>
              <th scope="col">{t("adminColState")}</th><th scope="col">{t("adminColActions")}</th>
            </tr></thead>
            <tbody>
              {items.map((u) => (
                <tr key={u.id}>
                  <td>{u.email ?? "-"}</td>
                  <td>{u.role}</td>
                  <td><span className={`badge ${u.disabled ? "badge-failed" : "badge-indexed"}`}>{u.disabled ? t("adminDisabled") : t("adminActive")}</span></td>
                  <td className="admin-actions">
                    {!u.disabled && <button type="button" className="btn btn-danger" onClick={() => setTarget(u)}>{t("adminDisable")}</button>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {target && (
        <ConfirmDialog
          message={`${t("adminConfirmDisable")} (${target.email ?? target.id})`}
          onCancel={() => setTarget(null)}
          onConfirm={() => { const id = target.id; setTarget(null); void run(() => admin.disableUser(id)); }}
        />
      )}
    </section>
  );
}
