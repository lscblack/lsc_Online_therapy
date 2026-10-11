import { useEffect, useState, type FormEvent } from "react";
import { profile } from "../../api/profile";
import type { AgeBand, ProfileUpdate } from "../../api/types";
import { useAuth } from "../../auth/useAuth";
import { useT, type Lang, type TKey } from "../../i18n/useT";
import { markOnboarded } from "./onboarded";
import "./onboarding.css";

const AGE_OPTIONS: [AgeBand, TKey][] = [
  ["under15", "obAgeUnder15"], ["15_17", "obAge1517"], ["18_19", "obAge1819"],
  ["20_24", "obAge2024"], ["25_plus", "obAge25"],
];
const GENDERS: [string, TKey][] = [["female", "obGenderFemale"], ["male", "obGenderMale"], ["nonbinary", "obGenderNonbinary"]];
const PRONOUNS = ["she/her", "he/him", "they/them"];
const PRONOUN_KEYS: TKey[] = ["obPronounsShe", "obPronounsHe", "obPronounsThey"];
const TONES: [string, TKey][] = [["casual", "obToneCasual"], ["gentle", "obToneGentle"], ["direct", "obToneDirect"]];
const INTERESTS: [string, TKey][] = [
  ["sleep", "obInterestSleep"], ["stress", "obInterestStress"], ["relationships", "obInterestRelationships"],
  ["nutrition", "obInterestNutrition"], ["sexual_health", "obInterestSexualHealth"], ["fitness", "obInterestFitness"],
];
const STEPS = 4;

export default function Onboarding({ onDone }: { onDone: () => void }) {
  const { t, lang, setLang } = useT();
  const { ensureAnon } = useAuth();
  const [step, setStep] = useState(0);
  const [nickname, setNickname] = useState("");
  const [age, setAge] = useState("");
  const [gender, setGender] = useState("");
  const [pronouns, setPronouns] = useState("");
  const [tone, setTone] = useState("");
  const [interests, setInterests] = useState<string[]>([]);
  const [sensitive, setSensitive] = useState("");
  const [busy, setBusy] = useState(false);
  const [failed, setFailed] = useState(false);

  // Create the anonymous identity up front so the user always has a session.
  useEffect(() => { ensureAnon().catch(() => { /* retried on finish */ }); }, [ensureAnon]);

  function buildPayload(): ProfileUpdate {
    const p: ProfileUpdate = {};
    if (nickname.trim()) p.nickname = nickname.trim();
    if (age) p.age_band = age as AgeBand;
    if (gender) p.gender = gender;
    if (pronouns) p.pronouns = pronouns;
    if (interests.length) p.interests = interests;
    if (tone) p.tone_pref = tone;
    if (sensitive.trim()) p.sensitive_context = sensitive.trim();
    return p;
  }

  async function finish() {
    setBusy(true); setFailed(false);
    try {
      await ensureAnon();
      const payload = buildPayload();
      if (Object.keys(payload).length > 0) await profile.put(payload);
      markOnboarded();
      onDone();
    } catch {
      setFailed(true);
    } finally {
      setBusy(false);
    }
  }

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (step < STEPS - 1) setStep(step + 1); else void finish();
  }
  const toggleInterest = (k: string) =>
    setInterests((xs) => (xs.includes(k) ? xs.filter((x) => x !== k) : [...xs, k]));
  const langs: [Lang, string][] = [["en", "English"], ["rw", "Kinyarwanda"]];

  return (
    <main className="page ob">
      <form className="ob-card" onSubmit={onSubmit} aria-busy={busy}>
        <div className="ob-buddy" aria-hidden="true">:)</div>
        <p className="ob-welcome">{t("obWelcome")}</p>
        <p className="ob-progress" aria-live="polite">{t("obStepOf")} {step + 1} / {STEPS}</p>

        <div className="ob-step" key={step}>
          {step === 0 && (
            <>
              <div className="ob-field">
                <label htmlFor="ob-nick">{t("obNickname")}</label>
                <input id="ob-nick" type="text" autoComplete="nickname" maxLength={40} value={nickname}
                  aria-describedby="ob-nick-hint" onChange={(e) => setNickname(e.target.value)} />
                <small id="ob-nick-hint">{t("obNicknameHint")}</small>
              </div>
              <div role="radiogroup" aria-label={t("obLanguage")} className="ob-field">
                <span className="ob-legend">{t("obLanguage")}</span>
                <div className="ob-chips">
                  {langs.map(([code, name]) => (
                    <button key={code} type="button" role="radio" aria-checked={lang === code} lang={code}
                      className={`ob-chip${lang === code ? " on" : ""}`} onClick={() => setLang(code)}>{name}</button>
                  ))}
                </div>
              </div>
            </>
          )}
          {step === 1 && (
            <>
              <h2>{t("obStepAbout")} <span className="ob-opt">({t("obOptional")})</span></h2>
              <div className="ob-field">
                <label htmlFor="ob-age">{t("obAge")}</label>
                <select id="ob-age" value={age} onChange={(e) => setAge(e.target.value)}>
                  <option value="">{t("obPreferNot")}</option>
                  {AGE_OPTIONS.map(([v, k]) => <option key={v} value={v}>{t(k)}</option>)}
                </select>
              </div>
              <div className="ob-field">
                <label htmlFor="ob-gender">{t("obGender")}</label>
                <select id="ob-gender" value={gender} onChange={(e) => setGender(e.target.value)}>
                  <option value="">{t("obPreferNot")}</option>
                  {GENDERS.map(([v, k]) => <option key={v} value={v}>{t(k)}</option>)}
                </select>
              </div>
              <div className="ob-field">
                <label htmlFor="ob-pron">{t("obPronouns")}</label>
                <select id="ob-pron" value={pronouns} onChange={(e) => setPronouns(e.target.value)}>
                  <option value="">{t("obPreferNot")}</option>
                  {PRONOUNS.map((v, i) => <option key={v} value={v}>{t(PRONOUN_KEYS[i])}</option>)}
                </select>
              </div>
            </>
          )}
          {step === 2 && (
            <>
              <h2>{t("obStepStyle")} <span className="ob-opt">({t("obOptional")})</span></h2>
              <div className="ob-field" role="group" aria-label={t("obToneLabel")}>
                <span className="ob-legend">{t("obToneLabel")}</span>
                <div className="ob-chips">
                  {TONES.map(([v, k]) => (
                    <button key={v} type="button" aria-pressed={tone === v}
                      className={`ob-chip${tone === v ? " on" : ""}`} onClick={() => setTone(tone === v ? "" : v)}>{t(k)}</button>
                  ))}
                </div>
              </div>
              <div className="ob-field" role="group" aria-label={t("obInterestsLabel")}>
                <span className="ob-legend">{t("obInterestsLabel")}</span>
                <div className="ob-chips">
                  {INTERESTS.map(([v, k]) => (
                    <button key={v} type="button" aria-pressed={interests.includes(v)}
                      className={`ob-chip${interests.includes(v) ? " on" : ""}`} onClick={() => toggleInterest(v)}>{t(k)}</button>
                  ))}
                </div>
              </div>
            </>
          )}
          {step === 3 && (
            <>
              <h2>{t("obStepPrivate")} <span className="ob-opt">({t("obOptional")})</span></h2>
              <div className="ob-note">{t("obSensitiveNote")}</div>
              <div className="ob-field">
                <label htmlFor="ob-sens">{t("obSensitiveLabel")}</label>
                <textarea id="ob-sens" rows={4} maxLength={1000} value={sensitive}
                  onChange={(e) => setSensitive(e.target.value)} />
              </div>
            </>
          )}
        </div>

        {failed && <p role="alert" className="ob-error">{t("obError")}</p>}

        <div className="ob-actions">
          {step > 0 && <button type="button" className="btn" onClick={() => setStep(step - 1)} disabled={busy}>{t("obBack")}</button>}
          <button type="button" className="btn" onClick={() => void finish()} disabled={busy}>{t("obSkip")}</button>
          <button type="submit" className="btn btn-primary" disabled={busy || (step === 0 && !nickname.trim())}>
            {busy ? t("obSaving") : step === STEPS - 1 ? t("obFinish") : t("obNext")}
          </button>
        </div>
      </form>
    </main>
  );
}
