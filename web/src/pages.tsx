import LangToggle from "./components/LangToggle";
import ThemeToggle from "./components/ThemeToggle";
import { useT } from "./i18n/useT";

export function Home() {
  const { t } = useT();
  return (
    <main className="page">
      <header className="bar">
        <h1>{t("appName")}</h1>
        <div className="bar-actions"><ThemeToggle /><LangToggle /></div>
      </header>
      <p className="lead">{t("greeting")}</p>
    </main>
  );
}

export function Admin() {
  const { t } = useT();
  return (
    <main className="page">
      <header className="bar">
        <h2>{t("adminTitle")}</h2>
        <div className="bar-actions"><ThemeToggle /><LangToggle /></div>
      </header>
      <p className="lead">{t("adminPlaceholder")}</p>
    </main>
  );
}
