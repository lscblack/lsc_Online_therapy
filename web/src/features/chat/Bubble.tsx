import { useT } from "../../i18n/useT";
import { CitationChips, CrisisPanel, ReferralCallout, isCrisis, needsReferral } from "./Callouts";
import type { ChatMessage } from "./types";

function Typing() {
  const { t } = useT();
  return (
    <span className="typing" role="status" aria-label={t("chatTyping")}>
      <span /><span /><span />
    </span>
  );
}

export default function Bubble({ message: m, onRetry }: { message: ChatMessage; onRetry: () => void }) {
  const { t } = useT();
  if (m.role === "user") {
    return <div className="row row-user"><div className="bubble bubble-user"><span className="sr-only">{t("chatYou")}: </span>{m.text}</div></div>;
  }
  const flags = m.meta?.safety_flags;
  const crisis = m.status === "done" && isCrisis(flags);
  const referral = m.status === "done" && !crisis && needsReferral(flags);
  const text = <p className="bubble-text">{m.text}</p>;
  return (
    <div className="row row-buddy">
      <div className="avatar" aria-hidden="true">U</div>
      <div className="bubble bubble-buddy">
        <span className="sr-only">{t("chatBuddy")}: </span>
        {crisis ? <CrisisPanel>{text}</CrisisPanel> : (m.text || m.status !== "streaming") && text}
        {m.status === "streaming" && <Typing />}
        {m.status === "done" && m.meta?.citations?.length ? <CitationChips citations={m.meta.citations} /> : null}
        {referral && <ReferralCallout />}
        {m.status === "error" && (
          <div className="chat-error" data-testid="chat-error">
            <span>{t("chatError")}</span>
            <button type="button" className="retry" onClick={onRetry}>{t("chatRetry")}</button>
          </div>
        )}
      </div>
    </div>
  );
}
