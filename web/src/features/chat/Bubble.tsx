import { useT } from "../../i18n/useT";
import { CitationChips, CrisisPanel, ReferralCallout, isCrisis, needsReferral } from "./Callouts";
import Markdown from "./Markdown";
import type { ChatMessage } from "./types";

function Typing() {
  const { t } = useT();
  return (
    <span className="typing" role="status" aria-label={t("chatTyping")}>
      <span /><span /><span />
    </span>
  );
}

const timeOf = (at: number | undefined): string =>
  at ? new Date(at).toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" }) : "";

function SeenTick({ seen }: { seen: boolean }) {
  return (
    <svg className={`tick${seen ? " tick-seen" : ""}`} viewBox="0 0 20 12" width="18" height="11" aria-hidden="true" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <path d="M2 6.5L5.5 10 12 2" />
      {seen && <path d="M8 10L14.5 2" />}
    </svg>
  );
}

export default function Bubble({ message: m, onRetry, seen = false }: { message: ChatMessage; onRetry: () => void; seen?: boolean }) {
  const { t } = useT();
  const time = timeOf(m.at);
  if (m.role === "user") {
    return (
      <div className="row row-user">
        <div className="row-col">
          <div className="bubble bubble-user"><span className="sr-only">{t("chatYou")}: </span>{m.text}</div>
          <div className="meta meta-user">
            {time && <span>{time}</span>}
            <span className="meta-status"><SeenTick seen={seen} />{seen ? t("chatSeen") : t("chatDelivered")}</span>
          </div>
        </div>
      </div>
    );
  }
  const flags = m.meta?.safety_flags;
  const crisis = m.status === "done" && isCrisis(flags);
  const referral = m.status === "done" && !crisis && needsReferral(flags);
  const text = <div className="bubble-md"><Markdown text={m.text} /></div>;
  return (
    <div className="row row-buddy">
      <div className="avatar" aria-hidden="true">U</div>
      <div className="row-col">
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
        {m.status === "done" && time && <div className="meta">{time}</div>}
      </div>
    </div>
  );
}
