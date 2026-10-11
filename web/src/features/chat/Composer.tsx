import { useState, type KeyboardEvent } from "react";
import { useT } from "../../i18n/useT";

export default function Composer({ disabled, onSend }: { disabled: boolean; onSend: (text: string) => void }) {
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
      <label htmlFor="chat-input" className="sr-only">{t("chatComposerLabel")}</label>
      <textarea
        id="chat-input" rows={1} value={value} disabled={disabled} placeholder={t("chatPlaceholder")}
        onChange={(e) => setValue(e.target.value)} onKeyDown={onKey}
      />
      <button type="submit" className="composer-send" disabled={disabled || !value.trim()}>{t("send")}</button>
    </form>
  );
}
