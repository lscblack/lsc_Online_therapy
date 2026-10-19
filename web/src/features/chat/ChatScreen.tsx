import { useCallback, useEffect, useRef, useState } from "react";
import { chat } from "../../api/chat";
import { ApiError } from "../../api/client";
import { profile } from "../../api/profile";
import { useT } from "../../i18n/useT";
import type { ChatResponse } from "../../api/types";
import Composer from "./Composer";
import MessageList from "./MessageList";
import VoicePanel from "../voice/VoicePanel";
import type { ChatMessage } from "./types";
import "./chat.css";
import "../voice/voice.css";

let seq = 0;
const nextId = () => `m${++seq}`;
/** Streaming endpoint unavailable (not a transient failure): fall back to the non-streaming call. */
const streamUnavailable = (e: unknown) => e instanceof ApiError && [404, 405, 501].includes(e.status);

export default function ChatScreen() {
  const { t, lang } = useT();
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [busy, setBusy] = useState(false);
  const [voiceOpen, setVoiceOpen] = useState(false);
  const [nickname, setNickname] = useState<string | null>(null);
  const convId = useRef<string | null>(null);
  const alive = useRef(true);
  const abort = useRef<AbortController | null>(null);

  useEffect(() => {
    alive.current = true;
    profile.get().then((p) => { if (alive.current) setNickname(p.nickname || null); }).catch(() => { /* welcome works without it */ });
    return () => { alive.current = false; abort.current?.abort(); };
  }, []);

  const patch = useCallback((id: string, fn: (m: ChatMessage) => ChatMessage) => {
    if (alive.current) setMessages((ms) => ms.map((m) => (m.id === id ? fn(m) : m)));
  }, []);

  const run = useCallback(async (userText: string, assistantId: string) => {
    setBusy(true);
    patch(assistantId, (m) => ({ ...m, text: "", status: "streaming", meta: undefined }));
    const req = { message: userText, conversation_id: convId.current, language: lang };
    const finish = (meta: ChatResponse | null, text: string) => {
      if (meta?.conversation_id) convId.current = meta.conversation_id;
      patch(assistantId, (m) => ({ ...m, text: text || m.text, status: "done", meta: meta ?? undefined }));
    };
    abort.current = new AbortController();
    try {
      const r = await chat.streamSend(req, (tok) => patch(assistantId, (m) => ({ ...m, text: m.text + tok })), abort.current.signal);
      finish(r.meta, r.message);
    } catch (e) {
      if (streamUnavailable(e)) {
        try { const r = await chat.send(req); finish(r, r.answer); }
        catch { patch(assistantId, (m) => ({ ...m, status: "error" })); }
      } else {
        patch(assistantId, (m) => ({ ...m, status: "error" }));
      }
    } finally {
      if (alive.current) setBusy(false);
    }
  }, [lang, patch]);

  const onSend = useCallback((text: string) => {
    const aid = nextId();
    const now = Date.now();
    setMessages((ms) => [...ms, { id: nextId(), role: "user", text, status: "done", at: now }, { id: aid, role: "assistant", text: "", status: "streaming", userText: text, at: now }]);
    void run(text, aid);
  }, [run]);

  const onRetry = useCallback((m: ChatMessage) => { if (m.userText) void run(m.userText, m.id); }, [run]);

  return (
    <main className="chat">
      <header className="chat-header">
        <div className="chat-header-id">
          <div className="chat-header-avatar" aria-hidden="true">U</div>
          <div className="chat-header-meta">
            <span className="chat-header-name">{t("appName")}</span>
            <span className="chat-header-presence"><i className="presence-dot" aria-hidden="true" />{t("chatPresence")}</span>
          </div>
        </div>
        <div className="chat-header-actions">
          <button type="button" className="chat-header-btn" aria-pressed={voiceOpen} onClick={() => setVoiceOpen((v) => !v)} title={voiceOpen ? t("voiceClose") : t("voiceOpen")}>
            <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z" /><path d="M19 10v2a7 7 0 0 1-14 0v-2" /><line x1="12" y1="19" x2="12" y2="23" />
            </svg>
            <span className="sr-only">{voiceOpen ? t("voiceClose") : t("voiceOpen")}</span>
          </button>
        </div>
      </header>
      <MessageList messages={messages} nickname={nickname} onRetry={onRetry} busy={busy} />
      {voiceOpen && <VoicePanel conversationId={convId.current} onConversationId={(id) => { convId.current = id; }} />}
      <Composer disabled={busy} onSend={onSend} onVoice={() => setVoiceOpen((v) => !v)} voiceOpen={voiceOpen} />
    </main>
  );
}
