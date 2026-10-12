import { useState } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "../../auth/useAuth";
import { useT } from "../../i18n/useT";
import LangToggle from "../../components/LangToggle";
import ThemeToggle from "../../components/ThemeToggle";
import Audit from "./Audit";
import Documents from "./Documents";
import Login from "./Login";
import Models from "./Models";
import Overview from "./Overview";
import Users from "./Users";
import "./admin.css";

type Section = "overview" | "docs" | "users" | "audit" | "models";

/** Admin dashboard: a professional shell — sidebar sections + a top bar + the active section.
 *  Reviewers (least privilege) only see Documents; full admins see everything. */
export default function AdminPanel() {
  const { t } = useT();
  const { isAdmin, role, adminLogout } = useAuth();
  const [section, setSection] = useState<Section>("overview");
  if (!isAdmin) return <main className="page"><Login /></main>;
  const full = role === "admin";

  const main: [Section, string][] = full
    ? [["overview", t("adminOverview")], ["docs", t("adminDocuments")], ["models", t("adminModels")]]
    : [["docs", t("adminDocuments")]];
  const manage: [Section, string][] = full ? [["users", t("adminUsers")], ["audit", t("adminAudit")]] : [];
  const all = [...main, ...manage];
  const active: Section = all.some(([k]) => k === section) ? section : "docs";
  const current = all.find(([k]) => k === active);
  const who = full ? t("adminRoleAdmin") : t("adminRoleReviewer");

  const NavItem = ({ k, label }: { k: Section; label: string }) => (
    <button type="button" className={`dash-link${active === k ? " active" : ""}`}
      aria-current={active === k ? "page" : undefined} onClick={() => setSection(k)}>{label}</button>
  );

  return (
    <div className="dash">
      <aside className="dash-side">
        <div className="dash-brand"><span className="nav-logo" aria-hidden="true">U</span>{t("adminConsole")}</div>
        <nav className="dash-nav" aria-label={t("adminConsole")}>
          <div className="dash-nav-group">{t("ovMainMenu")}</div>
          {main.map(([k, label]) => <NavItem key={k} k={k} label={label} />)}
          {manage.length > 0 && <div className="dash-nav-group">{t("ovManage")}</div>}
          {manage.map(([k, label]) => <NavItem key={k} k={k} label={label} />)}
        </nav>
        <div className="dash-side-card">
          <div className="dash-side-card-title">{t("ovKbTitle")}</div>
          <p className="muted">{t("ovKbBody")}</p>
          <button type="button" className="btn btn-sm btn-primary" onClick={() => setSection("docs")}>{t("adminDocuments")}</button>
        </div>
      </aside>

      <main className="dash-main">
        <header className="dash-top">
          <div className="dash-top-title">
            <span className="muted dash-crumb">{t("adminConsole")} ›</span>
            <h2>{current?.[1]}</h2>
          </div>
          <div className="dash-top-tools">
            <input className="dash-search" type="search" placeholder={t("ovSearch")} aria-label={t("ovSearch")} />
            <ThemeToggle />
            <LangToggle />
            <Link to="/" className="btn btn-sm dash-back">{t("ovBackToSite")}</Link>
            <div className="dash-profile">
              <span className="dash-avatar" aria-hidden="true">{(who[0] || "A").toUpperCase()}</span>
              <span className="dash-profile-meta">
                <span className="dash-profile-name">{who}</span>
                <span className="dash-profile-role">{full ? t("adminRoleAdmin") : t("adminRoleReviewer")}</span>
              </span>
            </div>
            <button type="button" className="btn btn-sm" onClick={adminLogout}>{t("logout")}</button>
          </div>
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
