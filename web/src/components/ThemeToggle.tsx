import { useTheme } from "../theme/ThemeProvider";
import { useT } from "../i18n/useT";

export default function ThemeToggle() {
  const { theme, toggle } = useTheme();
  const { t } = useT();
  const next = theme === "dark" ? t("themeLight") : t("themeDark");
  return (
    <button type="button" className="btn btn-ghost" onClick={toggle} aria-label={`${t("theme")}: ${next}`}>
      {theme === "dark" ? "☀" : "☾"} {next}
    </button>
  );
}
