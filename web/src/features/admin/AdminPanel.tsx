import { useState } from "react";
import { useAuth } from "../../auth/useAuth";
import { useT } from "../../i18n/useT";
import Audit from "./Audit";
import Documents from "./Documents";
import Login from "./Login";
import Users from "./Users";
import "./admin.css";

type Tab = "docs" | "users" | "audit";

/** Anything that is not exactly "admin" is treated as reviewer (least privilege). */
export default function AdminPanel() {
  const { t } = useT();
  const { isAdmin, role, adminLogout } = useAuth();
  const [tab, setTab] = useState<Tab>("docs");
  if (!isAdmin) return <Login />;
  const full = role === "admin";
  const active: Tab = !full ? "docs" : tab;
  const tabs: [Tab, string][] = [["docs", t("adminDocuments")], ...(full ? [["users", t("adminUsers")], ["audit", t("adminAudit")]] as [Tab, string][] : [])];
  return (
    <div className="admin">
      <div className="admin-head">
        <div role="tablist" className="admin-tabs">
          {tabs.map(([k, label]) => (
            <button key={k} role="tab" type="button" aria-selected={active === k} className={`btn${active === k ? " btn-primary" : ""}`} onClick={() => setTab(k)}>{label}</button>
          ))}
        </div>
        <button type="button" className="btn" onClick={adminLogout}>{t("logout")}</button>
      </div>
      {active === "docs" && <Documents canDelete={full} />}
      {full && active === "users" && <Users />}
      {full && active === "audit" && <Audit />}
    </div>
  );
}
