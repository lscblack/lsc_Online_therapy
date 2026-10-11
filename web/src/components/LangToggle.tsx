import { useT } from "../i18n/useT";

export default function LangToggle() {
  const { lang, setLang, t } = useT();
  return (
    <button type="button" className="btn btn-ghost" lang={lang === "en" ? "rw" : "en"}
      onClick={() => setLang(lang === "en" ? "rw" : "en")}
      aria-label={`${t("language")}: ${t("switchToLang")}`}>
      {t("switchToLang")}
    </button>
  );
}
