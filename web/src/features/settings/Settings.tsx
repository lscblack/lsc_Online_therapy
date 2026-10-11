import { useEffect, useRef, useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { profile } from "../../api/profile";
import type { AgeBand, Profile, ProfileUpdate } from "../../api/types";
import { useAuth } from "../../auth/useAuth";
import LangToggle from "../../components/LangToggle";
import Modal from "../../components/Modal";
import ThemeToggle from "../../components/ThemeToggle";
import { useT } from "../../i18n/useT";
import { resetOnboarding } from "../onboarding/onboarded";
import { AGE_OPTIONS, GENDERS, INTERESTS, PRONOUNS, PRONOUN_KEYS, TONES } from "../onboarding/options";
import "../onboarding/onboarding.css";
import "./settings.css";

interface Form { nickname: string; age: string; gender: string; pronouns: string; tone: string; interests: string[]; sensitive: string }
const EMPTY: Form = { nickname: "", age: "", gender: "", pronouns: "", tone: "", interests: [], sensitive: "" };
const fromProfile = (p: Profile): Form => ({
  nickname: p.nickname ?? "", age: p.age_band ?? "", gender: p.gender ?? "", pronouns: p.pronouns ?? "",
  tone: p.tone_pref ?? "", interests: p.interests ?? [], sensitive: p.sensitive_context ?? "",
});

/** Only fields the user changed are sent; a cleared field is sent as null. */
export function diff(base: Form, cur: Form): ProfileUpdate {
  const u: ProfileUpdate = {};
  const s = (a: string, b: string) => (a.trim() === b.trim() ? undefined : b.trim() || null);
  const nick = s(base.nickname, cur.nickname); if (nick !== undefined) u.nickname = nick;
  const age = s(base.age, cur.age); if (age !== undefined) u.age_band = age as AgeBand | null;
  const g = s(base.gender, cur.gender); if (g !== undefined) u.gender = g;
  const pr = s(base.pronouns, cur.pronouns); if (pr !== undefined) u.pronouns = pr;
  const tn = s(base.tone, cur.tone); if (tn !== undefined) u.tone_pref = tn;
  const sc = s(base.sensitive, cur.sensitive); if (sc !== undefined) u.sensitive_context = sc;
  if (base.interests.join("|") !== cur.interests.join("|")) u.interests = cur.interests;
  return u;
}

type Load = "loading" | "ready" | "error";

export default function Settings() {
  const { t } = useT();
  const { ensureAnon } = useAuth();
  const navigate = useNavigate();
  const [load, setLoad] = useState<Load>("loading");
  const [base, setBase] = useState<Form>(EMPTY);
  const [form, setForm] = useState<Form>(EMPTY);
  const [msg, setMsg] = useState<{ kind: "ok" | "err"; text: string } | null>(null);
  const [busy, setBusy] = useState(false);
  const [confirmWipe, setConfirmWipe] = useState(false);
  const alive = useRef(true);

  useEffect(() => {
    alive.current = true;
    (async () => {
      try {
        await ensureAnon();
        const f = fromProfile(await profile.get());
        if (!alive.current) return;
        setBase(f); setForm(f); setLoad("ready");
      } catch { if (alive.current) setLoad("error"); }
    })();
    return () => { alive.current = false; };
  }, [ensureAnon]);

  const set = <K extends keyof Form>(k: K, v: Form[K]) => setForm((f) => ({ ...f, [k]: v }));
  const toggleInterest = (k: string) =>
    set("interests", form.interests.includes(k) ? form.interests.filter((x) => x !== k) : [...form.interests, k]);

  async function onSave(e: FormEvent) {
    e.preventDefault();
    const payload = diff(base, form);
    setMsg(null);
    if (Object.keys(payload).length === 0) { setMsg({ kind: "ok", text: t("setSaved") }); return; }
    setBusy(true);
    try {
      await profile.put(payload);
      if (!alive.current) return;
      setBase(form);
      setMsg({ kind: "ok", text: t("setSaved") });
    } catch { if (alive.current) setMsg({ kind: "err", text: t("setSaveError") }); }
    finally { if (alive.current) setBusy(false); }
  }

  function rerun() { resetOnboarding(); navigate("/"); }

  async function doWipe() {
    setConfirmWipe(false); setBusy(true); setMsg(null);
    try {
      await profile.wipe();
      resetOnboarding();
      if (!alive.current) return;
      setBase(EMPTY); setForm(EMPTY);
      setMsg({ kind: "ok", text: t("setWipeDone") });
    } catch { if (alive.current) setMsg({ kind: "err", text: t("setWipeError") }); }
    finally { if (alive.current) setBusy(false); }
  }

  return (
    <main className="page settings">
      <h1>{t("setTitle")}</h1>

      <section className="set-card" aria-labelledby="set-appearance">
        <h2 id="set-appearance">{t("setAppearance")}</h2>
        <div className="bar-actions"><ThemeToggle /><LangToggle /></div>
      </section>

      <section className="set-card" aria-labelledby="set-profile">
        <h2 id="set-profile">{t("setProfile")}</h2>
        {load === "loading" && <p role="status">{t("adminLoading")}</p>}
        {load === "error" && <p role="alert" className="ob-error">{t("setLoadError")}</p>}
        {load === "ready" && (
          <form className="ob-step set-form" onSubmit={onSave} aria-busy={busy}>
            <div className="ob-field">
              <label htmlFor="st-nick">{t("obNickname")}</label>
              <input id="st-nick" type="text" maxLength={40} autoComplete="nickname" value={form.nickname}
                onChange={(e) => set("nickname", e.target.value)} />
            </div>
            <div className="ob-field">
              <label htmlFor="st-age">{t("obAge")}</label>
              <select id="st-age" value={form.age} onChange={(e) => set("age", e.target.value)}>
                <option value="">{t("obPreferNot")}</option>
                {AGE_OPTIONS.map(([v, k]) => <option key={v} value={v}>{t(k)}</option>)}
              </select>
            </div>
            <div className="ob-field">
              <label htmlFor="st-gender">{t("obGender")}</label>
              <select id="st-gender" value={form.gender} onChange={(e) => set("gender", e.target.value)}>
                <option value="">{t("obPreferNot")}</option>
                {GENDERS.map(([v, k]) => <option key={v} value={v}>{t(k)}</option>)}
              </select>
            </div>
            <div className="ob-field">
              <label htmlFor="st-pron">{t("obPronouns")}</label>
              <select id="st-pron" value={form.pronouns} onChange={(e) => set("pronouns", e.target.value)}>
                <option value="">{t("obPreferNot")}</option>
                {PRONOUNS.map((v, i) => <option key={v} value={v}>{t(PRONOUN_KEYS[i])}</option>)}
              </select>
            </div>
            <div className="ob-field" role="group" aria-label={t("obToneLabel")}>
              <span className="ob-legend">{t("obToneLabel")}</span>
              <div className="ob-chips">
                {TONES.map(([v, k]) => (
                  <button key={v} type="button" aria-pressed={form.tone === v}
                    className={`ob-chip${form.tone === v ? " on" : ""}`} onClick={() => set("tone", form.tone === v ? "" : v)}>{t(k)}</button>
                ))}
              </div>
            </div>
            <div className="ob-field" role="group" aria-label={t("obInterestsLabel")}>
              <span className="ob-legend">{t("obInterestsLabel")}</span>
              <div className="ob-chips">
                {INTERESTS.map(([v, k]) => (
                  <button key={v} type="button" aria-pressed={form.interests.includes(v)}
                    className={`ob-chip${form.interests.includes(v) ? " on" : ""}`} onClick={() => toggleInterest(v)}>{t(k)}</button>
                ))}
              </div>
            </div>
            <div className="ob-field">
              <label htmlFor="st-sens">{t("obSensitiveLabel")}</label>
              <textarea id="st-sens" rows={3} maxLength={1000} value={form.sensitive}
                onChange={(e) => set("sensitive", e.target.value)} />
              <small>{t("obSensitiveNote")}</small>
            </div>
            <div><button type="submit" className="btn btn-primary" disabled={busy}>{busy ? t("setSaving") : t("setSave")}</button></div>
          </form>
        )}
        {msg && <p role={msg.kind === "err" ? "alert" : "status"} className={msg.kind === "err" ? "ob-error" : "set-ok"}>{msg.text}</p>}
      </section>

      <section className="set-card">
        <p>{t("setRerunHint")}</p>
        <button type="button" className="btn" onClick={rerun}>{t("setRerun")}</button>
      </section>

      <section className="set-card set-danger">
        <p>{t("setWipeHint")}</p>
        <button type="button" className="btn btn-danger" disabled={busy} onClick={() => setConfirmWipe(true)}>{t("setWipe")}</button>
      </section>

      {confirmWipe && (
        <Modal title={t("setWipeConfirm")} onClose={() => setConfirmWipe(false)}>
          <p>{t("setWipeHint")}</p>
          <div className="modal-actions">
            <button type="button" className="btn" onClick={() => setConfirmWipe(false)}>{t("adminCancel")}</button>
            <button type="button" className="btn btn-danger" onClick={() => void doWipe()}>{t("setWipe")}</button>
          </div>
        </Modal>
      )}
    </main>
  );
}
