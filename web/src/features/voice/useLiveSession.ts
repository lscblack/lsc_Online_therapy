import { useCallback, useRef, useState } from "react";
import { voice } from "../../api/voice";
import { API_BASE } from "../../config";
import type { VoiceChatResponse } from "../../api/types";

export type LiveState = "idle" | "connecting" | "listening" | "thinking" | "speaking" | "error" | "ended";

export interface LiveTurn {
  role: "user" | "assistant";
  text: string;
  meta?: Partial<VoiceChatResponse>;
}

function wsUrl(path: string): string {
  const base = API_BASE.replace(/^http/, "ws");
  return `${base}${path}`;
}

/** Full-duplex live voice over WebRTC: streams mic to the backend, plays the agent's audio track,
 *  and renders live transcripts/answers from the control WebSocket. Supports barge-in. */
export function useLiveSession(language: string, audioEl: () => HTMLAudioElement | null) {
  const [state, setState] = useState<LiveState>("idle");
  const [partial, setPartial] = useState("");
  const [turns, setTurns] = useState<LiveTurn[]>([]);
  const [error, setError] = useState<string | null>(null);

  const pc = useRef<RTCPeerConnection | null>(null);
  const ws = useRef<WebSocket | null>(null);
  const stream = useRef<MediaStream | null>(null);
  const sessionId = useRef<string | null>(null);
  const active = useRef(false);

  const cleanup = useCallback(() => {
    active.current = false;
    try { ws.current?.close(); } catch { /* ignore */ }
    ws.current = null;
    try { pc.current?.getSenders().forEach((s) => s.track?.stop()); } catch { /* ignore */ }
    try { pc.current?.close(); } catch { /* ignore */ }
    pc.current = null;
    stream.current?.getTracks().forEach((t) => t.stop());
    stream.current = null;
    sessionId.current = null;
    const el = audioEl();
    if (el) el.srcObject = null;
  }, [audioEl]);

  const handleEvent = useCallback((ev: Record<string, unknown>) => {
    switch (ev.type) {
      case "state":
        setState(String(ev.state) as LiveState);
        break;
      case "transcript_partial":
        setPartial(String(ev.text ?? ""));
        break;
      case "transcript_final":
        setPartial("");
        if (ev.text) setTurns((t) => [...t, { role: "user", text: String(ev.text) }]);
        break;
      case "answer":
        setTurns((t) => [...t, { role: "assistant", text: String(ev.text ?? ""),
          meta: { language: String(ev.language ?? language), conversation_id: String(ev.conversation_id ?? "") } as Partial<VoiceChatResponse> }]);
        break;
      case "citations":
        setTurns((t) => attachToLastAssistant(t, { citations: (ev.citations as never) }));
        break;
      case "safety_flags":
        setTurns((t) => attachToLastAssistant(t, { safety_flags: (ev.safety_flags as never) }));
        break;
      case "error":
        setError(String(ev.code ?? "error"));
        break;
      default:
        break;
    }
  }, [language]);

  const start = useCallback(async () => {
    if (active.current) return;
    setError(null); setTurns([]); setPartial(""); setState("connecting");
    active.current = true;
    try {
      if (!navigator.mediaDevices?.getUserMedia || typeof RTCPeerConnection === "undefined") {
        setError("unsupported"); setState("error"); active.current = false; return;
      }
      const s = await navigator.mediaDevices.getUserMedia({ audio: true });
      stream.current = s;
      const peer = new RTCPeerConnection({ iceServers: [{ urls: "stun:stun.l.google.com:19302" }] });
      pc.current = peer;
      s.getTracks().forEach((tr) => peer.addTrack(tr, s));
      peer.ontrack = (e) => { const el = audioEl(); if (el) { el.srcObject = e.streams[0]; void el.play().catch(() => {}); } };
      peer.onicecandidate = (e) => {
        if (e.candidate && sessionId.current) void voice.liveIce(sessionId.current, e.candidate.toJSON()).catch(() => {});
      };
      const offer = await peer.createOffer({ offerToReceiveAudio: true });
      await peer.setLocalDescription(offer);
      const ans = await voice.liveOffer(offer.sdp ?? "", language);
      if (!active.current) { cleanup(); return; }
      sessionId.current = ans.session_id;
      await peer.setRemoteDescription({ type: "answer", sdp: ans.sdp });
      const socket = new WebSocket(wsUrl(`/v1/live?session_id=${encodeURIComponent(ans.session_id)}&ticket=${encodeURIComponent(ans.ws_ticket)}`));
      ws.current = socket;
      socket.onmessage = (m) => { try { handleEvent(JSON.parse(m.data)); } catch { /* ignore */ } };
      socket.onerror = () => { if (active.current) setError("error"); };
      socket.onclose = () => { if (active.current) { setState("ended"); cleanup(); } };
    } catch (e) {
      const name = (e as { name?: string })?.name;
      setError(name === "NotAllowedError" ? "denied" : name === "NotFoundError" ? "unsupported" : "error");
      setState("error");
      cleanup();
    }
  }, [language, audioEl, handleEvent, cleanup]);

  const interrupt = useCallback(() => {
    try { ws.current?.send(JSON.stringify({ type: "barge_in" })); } catch { /* ignore */ }
  }, []);

  const stop = useCallback(() => {
    try { ws.current?.send(JSON.stringify({ type: "end" })); } catch { /* ignore */ }
    setState("ended");
    cleanup();
  }, [cleanup]);

  return { state, partial, turns, error, start, stop, interrupt };
}

function attachToLastAssistant(turns: LiveTurn[], extra: Partial<VoiceChatResponse>): LiveTurn[] {
  for (let i = turns.length - 1; i >= 0; i--) {
    if (turns[i].role === "assistant") {
      const copy = turns.slice();
      copy[i] = { ...copy[i], meta: { ...copy[i].meta, ...extra } };
      return copy;
    }
  }
  return turns;
}
