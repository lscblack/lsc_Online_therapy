import { useState, type FormEvent } from "react";
import { useAuth } from "../../auth/useAuth";
import { useT } from "../../i18n/useT";
import { adminErrorKey } from "./adminErrors";

export default function Login() {
  const { t } = useT();
  const { adminLogin } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true); setErr(null);
    try { await adminLogin(email.trim(), password); }
    catch (x) { setErr(t(adminErrorKey(x, "login"))); }
    finally { setBusy(false); }
  }
  return (
    <form className="admin-card admin-login" onSubmit={submit}>
      <h3>{t("adminSignIn")}</h3>
      <label className="field">{t("adminEmail")}
        <input type="email" autoComplete="username" required value={email} onChange={(e) => setEmail(e.target.value)} />
      </label>
      <label className="field">{t("adminPassword")}
        <input type="password" autoComplete="current-password" required value={password} onChange={(e) => setPassword(e.target.value)} />
      </label>
      {err && <p role="alert" className="admin-error">{err}</p>}
      <button type="submit" className="btn btn-primary" disabled={busy}>{t("login")}</button>
    </form>
  );
}
