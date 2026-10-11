import { useState } from "react";
import { NavLink, Outlet } from "react-router-dom";
import LangToggle from "../components/LangToggle";
import ThemeToggle from "../components/ThemeToggle";
import { useT } from "../i18n/useT";
import "./layout.css";

/** App shell: header with nav links + theme/lang toggles; a collapsible menu on narrow screens. */
export default function Layout() {
  const { t } = useT();
  const [open, setOpen] = useState(false);
  const close = () => setOpen(false);
  return (
    <div className="shell">
      <header className="nav">
        <div className="nav-inner">
          <NavLink to="/" className="nav-brand" onClick={close}>
            <span className="nav-logo" aria-hidden="true">U</span>{t("appName")}
          </NavLink>
          <button type="button" className="btn btn-ghost nav-burger" aria-expanded={open} aria-controls="nav-menu"
            onClick={() => setOpen((o) => !o)}>{t("navMenu")}</button>
          <div id="nav-menu" className={`nav-menu${open ? " open" : ""}`}>
            <nav aria-label={t("navMain")} className="nav-links">
              <NavLink to="/" end onClick={close}>{t("navHome")}</NavLink>
              <NavLink to="/chat" onClick={close}>{t("navChat")}</NavLink>
              <NavLink to="/settings" onClick={close}>{t("settings")}</NavLink>
              <NavLink to="/admin" onClick={close}>{t("navAdmin")}</NavLink>
            </nav>
            <div className="nav-tools"><ThemeToggle /><LangToggle /></div>
          </div>
        </div>
      </header>
      <div className="shell-body"><Outlet /></div>
    </div>
  );
}
