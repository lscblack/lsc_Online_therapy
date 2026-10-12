import { useCallback, useEffect, useRef } from "react";
import { useT } from "../../i18n/useT";
import Bubble from "../chat/Bubble";
import { useLiveSession, type LiveState } from "./useLiveSession";

const STATE_KEY: Record<LiveState, string> = {
  idle: "voiceLiveIdle", connecting: "voiceLiveConnecting", listening: "voiceLiveListening",
  thinking: "voiceLiveThinking", speaking: "voiceLiveSpeaking", error: "voiceError", ended: "voiceLiveIdle",
};

/** Full-duplex live voice: start a WebRTC session, see live transcripts, interrupt (barge-in). */
export default function LivePanel({ onConversationId }: { onConversationId: (id: string) => void }) {
  const { t, lang } = useT();
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const getAudio = useCallback(() => audioRef.current, []);
  const live = useLiveSession(lang, getAudio);

  // Surface a conversation id from any assistant turn so chat history stays linked.
  useEffect(() => {
    const cid = live.turns.find((tn) => tn.meta?.conversation_id)?.meta?.conversation_id;
    if (cid) onConversationId(cid);
  }, [live.turns, onConversationId]);

  // End the session if the panel unmounts.
  useEffect(() => () => { live.stop(); }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const running = live.state !== "idle" && live.state !== "ended" && live.state !== "error";
  const speaking = live.state === "speaking";

  return (
    <section className="voice live-panel" aria-label={t("voicePanelLabel")}>
      {/* Mic streams to the backend over WebRTC; the answer is spoken by the browser's built-in
          TTS (free, no paid key), so the backend audio track is muted to avoid double audio. */}
      <audio ref={audioRef} autoPlay hidden muted />

      <div className="live-turns" data-testid="live-turns">
        {live.turns.map((tn, i) => (
          <Bubble key={i} onRetry={() => {}}
            message={{ id: `l${i}`, role: tn.role, text: tn.text, status: "done", meta: tn.meta as never }} />
        ))}
        {live.partial && (
          <p className="live-partial" aria-live="polite"><span className="live-dot" /> {live.partial}</p>
        )}
      </div>

      <div className="live-controls">
        <div className={`live-state live-state-${live.state}`} role="status" aria-live="polite">
          <span className="live-orb" aria-hidden="true" />
          {t(STATE_KEY[live.state] as never)}
        </div>

        {!running ? (
          <button type="button" className="btn btn-primary" onClick={() => void live.start()}>
            {t("voiceLiveStart")}
          </button>
        ) : (
          <div className="live-actions">
            <button type="button" className="btn" disabled={!speaking} onClick={live.interrupt}>
              {t("voiceInterrupt")}
            </button>
            <button type="button" className="btn btn-danger" onClick={live.stop}>{t("voiceLiveEnd")}</button>
          </div>
        )}

        {live.error && (
          <p className="voice-problem" role="alert">
            {live.error === "denied" ? t("voiceDenied") : live.error === "unsupported" ? t("voiceUnsupported") : t("voiceError")}
          </p>
        )}
      </div>
    </section>
  );
}
