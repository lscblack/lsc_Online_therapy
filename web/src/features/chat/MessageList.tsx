import { Fragment, useEffect, useRef } from "react";
import { useT } from "../../i18n/useT";
import Bubble from "./Bubble";
import type { ChatMessage } from "./types";

interface Props { messages: ChatMessage[]; nickname: string | null; onRetry: (m: ChatMessage) => void; busy: boolean }

/** Label for a day separator: "Today" when it is the current day, else a short date. */
function dayLabel(at: number | undefined, today: string): string {
  if (!at) return today;
  const d = new Date(at);
  const now = new Date();
  const sameDay = d.getFullYear() === now.getFullYear() && d.getMonth() === now.getMonth() && d.getDate() === now.getDate();
  return sameDay ? today : d.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}
const dayKey = (at: number | undefined): string => (at ? new Date(at).toDateString() : "today");

export default function MessageList({ messages, nickname, onRetry, busy }: Props) {
  const { t } = useT();
  const end = useRef<HTMLDivElement>(null);
  useEffect(() => { end.current?.scrollIntoView?.({ block: "end" }); }, [messages]);
  return (
    <div className="thread" role="log" aria-live="polite" aria-relevant="additions text" aria-busy={busy} aria-label={t("chatThreadLabel")}>
      {messages.length === 0 && (
        <div className="welcome">
          <div className="welcome-buddy" aria-hidden="true">U</div>
          <h2>{nickname ? t("chatWelcomeNamed").replace("{name}", nickname) : t("chatWelcome")}</h2>
          <p>{t("chatWelcomeHint")}</p>
        </div>
      )}
      {messages.map((m, i) => {
        const prev = messages[i - 1];
        const newDay = i === 0 || dayKey(prev?.at) !== dayKey(m.at);
        // A user message is "seen" once its paired assistant reply has text / is done.
        const reply = m.role === "user" ? messages[i + 1] : undefined;
        const seen = !!reply && reply.role === "assistant" && (reply.status === "done" || reply.text.length > 0);
        return (
          <Fragment key={m.id}>
            {newDay && <div className="day-sep"><span>{dayLabel(m.at, t("chatToday"))}</span></div>}
            <Bubble message={m} onRetry={() => onRetry(m)} seen={seen} />
          </Fragment>
        );
      })}
      <div ref={end} />
    </div>
  );
}
