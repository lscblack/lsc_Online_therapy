import { useState } from "react";
import { useAuth } from "../../auth/useAuth";
import { useT } from "../../i18n/useT";
import Audit from "./Audit";
import Documents from "./Documents";
import Login from "./Login";
import Models from "./Models";
import Overview from "./Overview";
import Users from "./Users";
import "./admin.css";

type Section = "overview" | "docs" | "users" | "audit" | "models";

/** Admin dashboard: a sidebar of sections + the active section. Reviewers (least privilege)
 *  only see Documents; full admins see everything, including model management. */
export default function AdminPanel() {
  const { t } = useT();
  const { isAdmin, role, adminLogout } = useAuth();
  const [section, setSection] = useState<Section>("overview");
  if (!isAdmin) return <main className="page"><Login /></main>;
  const full = role === "admin";

  const items: [Section, string][] = full
    ? [["overview", t("adminOverview")], ["docs", t("adminDocuments")], ["users", t("adminUsers")],
       ["audit", t("adminAudit")], ["models", t("adminModels")]]
    : [["docs", t("adminDocuments")]];
  const active: Section = items.some(([k]) => k === section) ? section : "docs";
  const current = items.find(([k]) => k === active);

  return (
    <div className="dash">
      <aside className="dash-side">
        <div className="dash-brand"><span className="nav-logo" aria-hidden="true">U</span>{t("adminConsole")}</div>
        <nav className="dash-nav" aria-label={t("adminConsole")}>
          {items.map(([k, label]) => (
            <button key={k} type="button" className={`dash-link${active === k ? " active" : ""}`}
              aria-current={active === k ? "page" : undefined} onClick={() => setSection(k)}>
              {label}
            </button>
          ))}
        </nav>
        <div className="dash-side-foot">
          <span className={`badge ${full ? "badge-green" : ""}`}>{full ? t("adminRoleAdmin") : t("adminRoleReviewer")}</span>
          <button type="button" className="btn btn-sm" onClick={adminLogout}>{t("logout")}</button>
        </div>
      </aside>

      <main className="dash-main">
        <header className="dash-head">
          <h2>{current?.[1]}</h2>
        </header>
        <div className="dash-content">
          {active === "overview" && full && <Overview onGo={setSection} />}
          {active === "docs" && <Documents canDelete={full} />}
          {active === "users" && full && <Users />}
          {active === "audit" && full && <Audit />}
          {active === "models" && full && <Models />}
        </div>
      </main>
    </div>
  );
}
