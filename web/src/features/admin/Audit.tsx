import { admin } from "../../api/admin";
import type { AuditEntry } from "../../api/types";
import { useT } from "../../i18n/useT";
import { useAdminList } from "./useAdminList";

const load = () => admin.listAudit();

export default function Audit() {
  const { t } = useT();
  const { items, loading, err, refresh } = useAdminList<AuditEntry>(load);
  return (
    <section aria-label={t("adminAudit")}>
      <div className="admin-toolbar"><button type="button" className="btn" onClick={() => void refresh()}>{t("adminRefresh")}</button></div>
      {err && <p role="alert" className="admin-error">{err}</p>}
      {loading && <p className="lead">{t("adminLoading")}</p>}
      {!loading && !err && items.length === 0 && <p className="lead">{t("adminEmpty")}</p>}
      {items.length > 0 && (
        <div className="table-wrap">
          <table className="admin-table">
            <thead><tr>
              <th scope="col">{t("adminColActor")}</th><th scope="col">{t("adminColAction")}</th>
              <th scope="col">{t("adminColTarget")}</th><th scope="col">{t("adminColTime")}</th>
            </tr></thead>
            <tbody>
              {items.map((a) => (
                <tr key={a.id}>
                  <td>{a.actor_id ?? "-"}</td><td>{a.action}</td><td>{a.target ?? "-"}</td>
                  <td><time dateTime={a.at}>{new Date(a.at).toLocaleString()}</time></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
