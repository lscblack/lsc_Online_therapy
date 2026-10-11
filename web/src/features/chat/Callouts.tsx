import type { ReactNode } from "react";
import { useT } from "../../i18n/useT";
import type { Citation, SafetyFlags } from "../../api/types";

function Icon({ kind }: { kind: "heart" | "info" }) {
  return (
    <svg className="callout-icon" viewBox="0 0 24 24" width="22" height="22" aria-hidden="true" focusable="false" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      {kind === "heart"
        ? <path d="M12 21s-7-4.5-9.3-9A5.3 5.3 0 0 1 12 6.6 5.3 5.3 0 0 1 21.3 12C19 16.5 12 21 12 21z" />
        : <><circle cx="12" cy="12" r="9" /><path d="M12 11v5M12 8h.01" /></>}
    </svg>
  );
}

/** Calm, caring crisis treatment: the supportive message leads; never a red/alert style. */
export function CrisisPanel({ children }: { children: ReactNode }) {
  const { t } = useT();
  return (
    <section className="callout callout-care" data-testid="callout-crisis" aria-label={t("chatCrisisTitle")}>
      <div className="callout-head"><Icon kind="heart" /><strong>{t("chatCrisisTitle")}</strong></div>
      <div className="callout-message">{children}</div>
      <p className="callout-next">{t("chatCrisisNext")}</p>
    </section>
  );
}

export function ReferralCallout() {
  const { t } = useT();
  return (
    <aside className="callout callout-soft" data-testid="callout-referral" aria-label={t("chatReferralTitle")}>
      <div className="callout-head"><Icon kind="info" /><strong>{t("chatReferralTitle")}</strong></div>
      <p>{t("chatReferralBody")}</p>
    </aside>
  );
}

export const isCrisis = (f: SafetyFlags | undefined) => f?.crisis === true;
export const needsReferral = (f: SafetyFlags | undefined) => !!f && (f.needs_referral === true || f.in_knowledge === false);

export function citationTitle(c: Citation): string | null {
  for (const k of ["title", "document_title", "source", "source_filename", "name"]) {
    const v = c[k];
    if (typeof v === "string" && v.trim()) return v.trim();
  }
  return null;
}

export function CitationChips({ citations }: { citations: Citation[] }) {
  const { t } = useT();
  const titles = citations.map(citationTitle).filter((x): x is string => !!x);
  if (!titles.length) return null;
  return (
    <ul className="chips" aria-label={t("chatSourcesLabel")}>
      {titles.map((title, i) => <li key={i} className="src-chip">{t("chatSource")}: {title}</li>)}
    </ul>
  );
}
