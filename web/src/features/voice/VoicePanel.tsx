import { useCallback, useEffect, useRef, useState } from "react";
import { voice } from "../../api/voice";
import type { VoiceChatResponse } from "../../api/types";
import { useT } from "../../i18n/useT";
import Bubble from "../chat/Bubble";
import { useReplyAudio } from "./useReplyAudio";
import "./voice.css";

type Phase = "idle" | "recording" | "processing";
type Problem = "denied" | "unsupported" | "error" | null;

function fmt(s: number) { return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`; }

interface Props { conversationId: string | null; onConversationId: (id: string) => void }

export default function VoicePanel({ conversationId, onConversationId }: Props) {
  const { t, lang } = useT();
  const [phase, setPhase] = useState<Phase>("idle");
  const [problem, setProblem] = useState<Problem>(null);
  const [result, setResult] = useState<VoiceChatResponse | null>(null);
  const [elapsed, setElapsed] = useState(0);
  const recorder = useRef<MediaRecorder | null>(null);
  const stream = useRef<MediaStream | null>(null);
  const timer = useRef<ReturnType<typeof setInterval> | null>(null);
  const alive = useRef(true);
  const convRef = useRef(conversationId);
  convRef.current = conversationId;
  const audio = useReplyAudio(result);

  const release = useCallback(() => {
    if (timer.current) { clearInterval(timer.current); timer.current = null; }
    stream.current?.getTracks().forEach((tr) => tr.stop());
    stream.current = null;
  }, []);

  useEffect(() => {
    alive.current = true;
    return () => {
      alive.current = false;
      const r = recorder.current;
      if (r) { r.ondataavailable = null; r.onstop = null; try { if (r.state !== "inactive") r.stop(); } catch { /* already stopped */ } }
      recorder.current = null;
      release();
    };
  }, [release]);

  const send = useCallback(async (blob: Blob) => {
    try {
      const r = await voice.chat(blob, { conversation_id: convRef.current, language: lang });
      if (!alive.current) return;
      if (r.conversation_id) onConversationId(r.conversation_id);
      setResult(r);
    } catch {
      if (alive.current) setProblem("error");
    } finally {
      if (alive.current) setPhase("idle");
    }
  }, [lang, onConversationId]);

  const start = async () => {
    setProblem(null);
    if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === "undefined") { setProblem("unsupported"); return; }
    let s: MediaStream;
    try {
      s = await navigator.mediaDevices.getUserMedia({ audio: true });
    } catch (e) {
      const name = (e as { name?: string })?.name;
      setProblem(name === "NotFoundError" || name === "NotSupportedError" ? "unsupported" : "denied");
      return;
    }
    if (!alive.current) { s.getTracks().forEach((tr) => tr.stop()); return; }
    stream.current = s;
    const chunks: Blob[] = [];
    const rec = new MediaRecorder(s);
    rec.ondataavailable = (e) => { if (e.data && e.data.size > 0) chunks.push(e.data); };
    rec.onstop = () => {
      release();
      recorder.current = null;
      if (!alive.current) return;
      setPhase("processing");
      void send(new Blob(chunks, { type: rec.mimeType || "audio/webm" }));
    };
    recorder.current = rec;
    rec.start();
    setElapsed(0);
    timer.current = setInterval(() => setElapsed((n) => n + 1), 1000);
    setPhase("recording");
  };

  const stop = () => { try { recorder.current?.stop(); } catch { release(); setPhase("idle"); } };
  const recording = phase === "recording";
  const busy = phase === "processing";
  const status = recording ? `${t("voiceRecording")} (${fmt(elapsed)})` : busy ? t("voiceProcessing") : t("voiceIdleHint");

  return (
    <section className="voice" aria-label={t("voicePanelLabel")}>
      {result && (
        <div className="voice-result" data-testid="voice-result">
          <Bubble message={{ id: "vu", role: "user", text: result.transcript, status: "done" }} onRetry={() => {}} />
          <Bubble message={{ id: "vb", role: "assistant", text: result.answer, status: "done", meta: result }} onRetry={() => {}} />
          {audio.available && (
            <div className="voice-audio">
              <button type="button" className="voice-chip" onClick={audio.replay}>{t("voiceReplay")}</button>
              <button type="button" className="voice-chip" aria-pressed={audio.muted} onClick={audio.toggleMute}>
                {audio.muted ? t("voiceUnmute") : t("voiceMute")}
              </button>
            </div>
          )}
        </div>
      )}
      <div className="voice-controls">
        <button
          type="button" className={`rec-btn${recording ? " is-recording" : ""}`}
          aria-pressed={recording} aria-label={recording ? t("voiceStop") : t("voiceStart")}
          disabled={busy} onClick={recording ? stop : () => void start()}
        >
          <svg viewBox="0 0 24 24" width="28" height="28" aria-hidden="true" focusable="false" fill="currentColor">
            {recording ? <rect x="6" y="6" width="12" height="12" rx="2" /> : <path d="M12 15a3 3 0 0 0 3-3V6a3 3 0 0 0-6 0v6a3 3 0 0 0 3 3zm5-3a5 5 0 0 1-10 0H5a7 7 0 0 0 6 6.9V22h2v-3.1A7 7 0 0 0 19 12h-2z" />}
          </svg>
        </button>
        <p className="voice-status" role="status" aria-live="polite">{status}</p>
        {problem && (
          <p className="voice-problem" role={problem === "error" ? "alert" : "status"}>
            {problem === "denied" ? t("voiceDenied") : problem === "unsupported" ? t("voiceUnsupported") : t("voiceError")}
          </p>
        )}
        <button type="button" className="voice-live" disabled aria-disabled="true">
          {t("voiceLive")} <span className="voice-soon">{t("voiceLiveSoon")}</span>
        </button>
      </div>
    </section>
  );
}
