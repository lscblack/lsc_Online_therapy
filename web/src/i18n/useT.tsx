import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { readStore, writeStore } from "../storage";
import en, { type Dict } from "./en";
import rw from "./rw";

export type Lang = "en" | "rw";
export type TKey = keyof Dict;
const dicts: Record<Lang, Dict> = { en, rw };
export const LANG_KEY = "ubuzima.lang";

interface LangCtx {
  lang: Lang;
  setLang: (l: Lang) => void;
  t: (key: TKey) => string;
}
const Ctx = createContext<LangCtx | null>(null);

export function LangProvider({ children }: { children: ReactNode }) {
  const [lang, setLangState] = useState<Lang>(() => (readStore(LANG_KEY) === "rw" ? "rw" : "en"));
  useEffect(() => { document.documentElement.lang = lang; }, [lang]);
  const setLang = useCallback((l: Lang) => { setLangState(l); writeStore(LANG_KEY, l); }, []);
  const t = useCallback((key: TKey) => dicts[lang][key], [lang]);
  const value = useMemo(() => ({ lang, setLang, t }), [lang, setLang, t]);
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useT(): LangCtx {
  const c = useContext(Ctx);
  if (!c) throw new Error("useT must be used within LangProvider");
  return c;
}
