import { Link } from "react-router-dom";
import { useT } from "../../i18n/useT";
import { Icon } from "./icons";
import { LANDING } from "./copy";
import "./landing.css";

/** Public landing page: project info + infographics, with CTAs into the chat app and admin. */
export default function Landing() {
  const { lang } = useT();
  const c = LANDING[lang];
  return (
    <main className="landing">
      {/* Hero */}
      <section className="lx-hero">
        <div className="container lx-hero-inner">
          <div className="lx-hero-copy animate-in">
            <span className="badge badge-green lx-badge"><Icon name="leaf" size={16} /> {c.heroBadge}</span>
            <h1 className="lx-title">{c.heroTitle}</h1>
            <p className="lx-sub">{c.heroSub}</p>
            <div className="lx-cta">
              <Link to="/chat" className="btn btn-primary">{c.ctaStart}</Link>
              <a href="#how" className="btn btn-ghost">{c.ctaLearn}</a>
            </div>
          </div>
          <div className="lx-hero-art animate-in delay-2" aria-hidden="true">
            <div className="lx-chip lx-chip-1"><Icon name="chat" size={20} /></div>
            <div className="lx-chip lx-chip-2"><Icon name="mic" size={20} /></div>
            <div className="lx-chip lx-chip-3"><Icon name="shield" size={20} /></div>
            <div className="lx-orb"><Icon name="leaf" size={64} /></div>
          </div>
        </div>
      </section>

      {/* Stats / infographics */}
      <section className="container lx-stats">
        {c.stats.map((s, i) => (
          <div key={s.label} className={`lx-stat card animate-in delay-${(i % 4) + 1}`}>
            <div className="lx-stat-value">{s.value}</div>
            <div className="lx-stat-label muted">{s.label}</div>
          </div>
        ))}
      </section>

      {/* Features */}
      <section className="container lx-section">
        <h2 className="lx-h2">{c.featuresTitle}</h2>
        <div className="lx-grid">
          {c.features.map((f) => (
            <article key={f.title} className="lx-feature card">
              <span className="lx-feature-icon"><Icon name={f.icon} /></span>
              <h3>{f.title}</h3>
              <p className="muted">{f.body}</p>
            </article>
          ))}
        </div>
      </section>

      {/* How it works */}
      <section id="how" className="container lx-section">
        <h2 className="lx-h2">{c.stepsTitle}</h2>
        <ol className="lx-steps">
          {c.steps.map((st, i) => (
            <li key={st.title} className="lx-step card">
              <span className="lx-step-n">{i + 1}</span>
              <div><h3>{st.title}</h3><p className="muted">{st.body}</p></div>
            </li>
          ))}
        </ol>
      </section>

      {/* Safety + privacy */}
      <section className="container lx-split">
        <div className="lx-panel card">
          <span className="lx-feature-icon"><Icon name="shield" /></span>
          <h3>{c.safetyTitle}</h3>
          <p className="muted">{c.safetyBody}</p>
        </div>
        <div className="lx-panel card">
          <span className="lx-feature-icon"><Icon name="lock" /></span>
          <h3>{c.privacyTitle}</h3>
          <p className="muted">{c.privacyBody}</p>
        </div>
      </section>

      {/* Footer CTA */}
      <section className="lx-footer">
        <div className="container lx-footer-inner">
          <div>
            <h2 className="lx-footer-title">{c.footerCta}</h2>
            <p className="muted lx-partner">{c.partner}</p>
          </div>
          <Link to="/chat" className="btn btn-primary">{c.footerStart}</Link>
        </div>
      </section>
    </main>
  );
}
