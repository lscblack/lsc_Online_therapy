import { useCallback, useEffect, useRef, useState } from "react";
import type { VoiceChatResponse } from "../../api/types";

function toBlob(b64: string, mime: string): Blob {
  const bin = atob(b64);
  const bytes = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
  return new Blob([bytes], { type: mime || "audio/mpeg" });
}

/** Decodes and plays the voice reply when TTS is available. Silent no-op otherwise. */
export function useReplyAudio(result: VoiceChatResponse | null) {
  const [muted, setMuted] = useState(false);
  const el = useRef<HTMLAudioElement | null>(null);
  const url = useRef<string | null>(null);
  const mutedRef = useRef(false);
  const available = !!result && result.tts_available === true && !!result.audio_base64;

  const teardown = useCallback(() => {
    el.current?.pause?.();
    el.current = null;
    if (url.current) { try { URL.revokeObjectURL(url.current); } catch { /* ignore */ } url.current = null; }
  }, []);

  const play = useCallback(() => {
    const a = el.current;
    if (!a || mutedRef.current) return;
    try { a.currentTime = 0; } catch { /* ignore */ }
    void Promise.resolve(a.play()).catch(() => { /* autoplay blocked: replay button still works */ });
  }, []);

  useEffect(() => {
    teardown();
    if (!result || !available) return;
    try {
      url.current = URL.createObjectURL(toBlob(result.audio_base64, result.audio_mime));
      el.current = new Audio(url.current);
      el.current.muted = mutedRef.current;
      play();
    } catch { teardown(); }
    return teardown;
  }, [result, available, play, teardown]);

  const toggleMute = () => {
    mutedRef.current = !mutedRef.current;
    setMuted(mutedRef.current);
    if (el.current) el.current.muted = mutedRef.current;
    if (mutedRef.current) el.current?.pause?.();
  };
  const replay = () => {
    if (!el.current) return;
    mutedRef.current = false; setMuted(false); el.current.muted = false;
    play();
  };
  return { available, muted, toggleMute, replay };
}
