import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { readStore, writeStore } from "../storage";

export type Theme = "light" | "dark";
export const THEME_KEY = "ubuzima.theme";

function systemTheme(): Theme {
  try {
    return window.matchMedia?.("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  } catch { return "light"; }
}

interface ThemeCtx { theme: Theme; setTheme: (t: Theme) => void; toggle: () => void; }
const Ctx = createContext<ThemeCtx | null>(null);

export function ThemeProvider({ children }: { children: ReactNode }) {
  // null = follow system (no data-theme attribute; CSS media query decides)
  const [chosen, setChosen] = useState<Theme | null>(() => {
    const s = readStore(THEME_KEY);
    return s === "light" || s === "dark" ? s : null;
  });
  const theme = chosen ?? systemTheme();
  useEffect(() => {
    const el = document.documentElement;
    if (chosen) el.setAttribute("data-theme", chosen); else el.removeAttribute("data-theme");
  }, [chosen]);
  const setTheme = useCallback((t: Theme) => { setChosen(t); writeStore(THEME_KEY, t); }, []);
  const toggle = useCallback(() => setTheme(theme === "dark" ? "light" : "dark"), [theme, setTheme]);
  const value = useMemo(() => ({ theme, setTheme, toggle }), [theme, setTheme, toggle]);
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useTheme(): ThemeCtx {
  const c = useContext(Ctx);
  if (!c) throw new Error("useTheme must be used within ThemeProvider");
  return c;
}
