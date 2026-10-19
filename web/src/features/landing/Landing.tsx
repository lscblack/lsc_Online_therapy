import { Link } from "react-router-dom";
import { useT } from "../../i18n/useT";
import { Icon } from "./icons";
import { LANDING } from "./copy";
import "./landing.css";

/** Public home page: full professional SRHR landing — hero, services, how it works, why, safety,
 *  FAQ and footer. Bilingual (EN/RW), animated, responsive. Content spans 11/12 of the viewport. */
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
              <Link to="/chat" className="btn btn-primary lx-cta-pill">{c.ctaStart}</Link>
              <Link to="/chat" className="btn lx-cta-ghost lx-cta-pill"><Icon name="mic" size={18} /> {c.ctaVoice}</Link>
            </div>
            <a href="#how" className="lx-learn-link">{c.ctaLearn}</a>
            <div className="lx-hero-stats">
              {c.stats.map((s) => (
                <div key={s.label} className="lx-hero-stat">
                  <div className="lx-hero-stat-v">{s.value}</div>
                  <div className="muted lx-hero-stat-l">{s.label}</div>
                </div>
              ))}
            </div>
          </div>
          <div className="lx-hero-art animate-in delay-2" aria-hidden="true">
            <div className="lx-chip lx-chip-1"><Icon name="chat" size={22} /></div>
            <div className="lx-chip lx-chip-2"><Icon name="mic" size={22} /></div>
            <div className="lx-chip lx-chip-3"><Icon name="shield" size={22} /></div>
            <div className="lx-chip lx-chip-4"><Icon name="globe" size={22} /></div>
            <div className="lx-orb"><Icon name="heart" size={72} /></div>
          </div>
        </div>
      </section>

      {/* Services */}
      <section className="container lx-section">
        <header className="lx-head">
          <h2 className="lx-h2">{c.servicesTitle}</h2>
          <p className="lead lx-head-sub">{c.servicesSub}</p>
        </header>
        <div className="lx-grid lx-grid-3">
          {c.services.map((s) => (
            <article key={s.title} className="lx-service card">
              <span className="lx-feature-icon"><Icon name={s.icon} /></span>
              <h3>{s.title}</h3>
              <p className="muted">{s.body}</p>
            </article>
          ))}
        </div>
      </section>

      {/* How it works */}
      <section id="how" className="container lx-section">
        <h2 className="lx-h2 lx-center">{c.stepsTitle}</h2>
        <ol className="lx-steps">
          {c.steps.map((st, i) => (
            <li key={st.title} className="lx-step card">
              <span className="lx-step-n">{i + 1}</span>
              <div><h3>{st.title}</h3><p className="muted">{st.body}</p></div>
            </li>
          ))}
        </ol>
      </section>

      {/* Why Ubuzima */}
      <section className="container lx-section">
        <div className="lx-why card">
          <div className="lx-why-copy">
            <h2 className="lx-h2">{c.whyTitle}</h2>
            <ul className="lx-check">
              {c.whyPoints.map((p) => (
                <li key={p}><span className="lx-check-i"><Icon name="check" size={16} /></span>{p}</li>
              ))}
            </ul>
          </div>
          <div className="lx-why-stat">
            <div className="lx-why-stat-v">{c.whyStat.value}</div>
            <div className="muted">{c.whyStat.label}</div>
            <Link to="/chat" className="btn btn-primary lx-why-cta">{c.ctaStart}</Link>
          </div>
        </div>
      </section>

      {/* Features */}
      <section className="container lx-section">
        <h2 className="lx-h2 lx-center">{c.featuresTitle}</h2>
        <div className="lx-grid lx-grid-3">
          {c.features.map((f) => (
            <article key={f.title} className="lx-feature card">
              <span className="lx-feature-icon"><Icon name={f.icon} /></span>
              <h3>{f.title}</h3>
              <p className="muted">{f.body}</p>
            </article>
          ))}
        </div>
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

      {/* FAQ */}
      <section className="container lx-section">
        <h2 className="lx-h2 lx-center">{c.faqTitle}</h2>
        <div className="lx-faq">
          {c.faqs.map((f) => (
            <details key={f.q} className="lx-faq-item card">
              <summary>{f.q}</summary>
              <p className="muted">{f.a}</p>
            </details>
          ))}
        </div>
      </section>

      {/* Footer CTA */}
      <section className="lx-cta-band">
        <div className="container lx-cta-inner">
          <div>
            <h2 className="lx-cta-title">{c.footerCta}</h2>
            <p className="lx-partner">{c.partner}</p>
          </div>
          <Link to="/chat" className="btn lx-cta-btn">{c.footerStart}</Link>
        </div>
      </section>

      {/* Footer */}
      <footer className="lx-footer">
        <div className="container lx-footer-inner">
          <div className="lx-footer-brand">
            <div className="nav-brand"><span className="nav-logo" aria-hidden="true">U</span>Ubuzima</div>
            <p className="muted">{c.footerTagline}</p>
          </div>
          {c.footerCols.map((col) => (
            <nav key={col.title} className="lx-footer-col" aria-label={col.title}>
              <h4>{col.title}</h4>
              {col.links.map((l) => (
                <Link key={l} to="/chat" className="lx-footer-link">{l}</Link>
              ))}
            </nav>
          ))}
        </div>
        <div className="container lx-footer-rights muted">{c.footerRights}</div>
      </footer>
    </main>
  );
}
