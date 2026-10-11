import { useEffect, useRef } from "react";
import { useT } from "../../i18n/useT";
import Bubble from "./Bubble";
import type { ChatMessage } from "./types";

interface Props { messages: ChatMessage[]; nickname: string | null; onRetry: (m: ChatMessage) => void; busy: boolean }

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
      {messages.map((m) => <Bubble key={m.id} message={m} onRetry={() => onRetry(m)} />)}
      <div ref={end} />
    </div>
  );
}
