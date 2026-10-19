import { useState, type KeyboardEvent } from "react";
import { useT } from "../../i18n/useT";

interface Props {
  disabled: boolean;
  onSend: (text: string) => void;
  onVoice?: () => void;
  voiceOpen?: boolean;
}

export default function Composer({ disabled, onSend, onVoice, voiceOpen }: Props) {
  const { t } = useT();
  const [value, setValue] = useState("");
  const submit = () => {
    const v = value.trim();
    if (!v || disabled) return;
    setValue("");
    onSend(v);
  };
  const onKey = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) { e.preventDefault(); submit(); }
  };
  return (
    <form className="composer" onSubmit={(e) => { e.preventDefault(); submit(); }}>
      <div className="composer-pill">
        {onVoice && (
          <button type="button" className="composer-mic" aria-pressed={voiceOpen} aria-label={t("chatVoiceJump")} onClick={onVoice}>
            <svg viewBox="0 0 24 24" width="22" height="22" aria-hidden="true" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
              <rect x="9" y="3" width="6" height="11" rx="3" /><path d="M5 11a7 7 0 0 0 14 0M12 18v3" />
            </svg>
          </button>
        )}
        <label htmlFor="chat-input" className="sr-only">{t("chatComposerLabel")}</label>
        <textarea
          id="chat-input" rows={1} value={value} disabled={disabled} placeholder={t("chatPlaceholder")}
          onChange={(e) => setValue(e.target.value)} onKeyDown={onKey}
        />
      </div>
      <button type="submit" className="composer-send" aria-label={t("send")} disabled={disabled || !value.trim()}>
        <svg viewBox="0 0 24 24" width="22" height="22" aria-hidden="true" fill="none" stroke="currentColor" strokeWidth="1.9" strokeLinecap="round" strokeLinejoin="round">
          <path d="M4 12l16-8-6 16-3-7-7-1z" />
        </svg>
      </button>
    </form>
  );
}
