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

/** Tiny inline nav icons (stroke = currentColor) so the sidebar needs no image assets. */
function NavIcon({ k }: { k: Section }) {
  const p = { fill: "none", stroke: "currentColor", strokeWidth: 1.8, strokeLinecap: "round" as const, strokeLinejoin: "round" as const };
  const s = { width: 18, height: 18, viewBox: "0 0 24 24", "aria-hidden": true } as const;
  switch (k) {
    case "overview": return <svg {...s}><rect {...p} x="3" y="3" width="8" height="8" rx="2" /><rect {...p} x="13" y="3" width="8" height="5" rx="2" /><rect {...p} x="13" y="10" width="8" height="11" rx="2" /><rect {...p} x="3" y="13" width="8" height="8" rx="2" /></svg>;
    case "docs": return <svg {...s}><path {...p} d="M6 3h8l4 4v14H6z" /><path {...p} d="M14 3v4h4M9 13h6M9 17h6" /></svg>;
    case "models": return <svg {...s}><rect {...p} x="7" y="7" width="10" height="10" rx="2" /><path {...p} d="M10 3v4M14 3v4M10 17v4M14 17v4M3 10h4M3 14h4M17 10h4M17 14h4" /></svg>;
    case "users": return <svg {...s}><circle {...p} cx="9" cy="8" r="3" /><path {...p} d="M3 20a6 6 0 0 1 12 0M16 11a3 3 0 0 0 0-6M21 20a6 6 0 0 0-5-5.9" /></svg>;
    case "audit": return <svg {...s}><path {...p} d="M5 4h11l3 3v13H5z" /><path {...p} d="M8 10h8M8 14h5" /></svg>;
    default: return null;
  }
}

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
      aria-current={active === k ? "page" : undefined} onClick={() => setSection(k)}>
      <span className="dash-link-icon" aria-hidden="true"><NavIcon k={k} /></span>{label}
    </button>
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
