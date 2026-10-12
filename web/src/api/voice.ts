import { apiFetch, apiFetchRaw } from "./client";
import type { LiveOfferResponse, TranscribeResponse, VoiceChatOptions, VoiceChatResponse } from "./types";

export const voice = {
  transcribe(blob: Blob, language?: string): Promise<TranscribeResponse> {
    const f = new FormData();
    f.append("audio", blob, "audio.webm");
    if (language) f.append("language", language);
    return apiFetch<TranscribeResponse>("/v1/voice/transcribe", { method: "POST", body: f });
  },
  /** Returns the synthesized audio as a Blob. */
  async speak(text: string, language: string, voiceName?: string): Promise<Blob> {
    const res = await apiFetchRaw("/v1/voice/speak", {
      method: "POST", body: { text, language, ...(voiceName ? { voice: voiceName } : {}) }, headers: { Accept: "audio/*" },
    });
    return res.blob();
  },
  chat(blob: Blob, opts: VoiceChatOptions = {}): Promise<VoiceChatResponse> {
    const f = new FormData();
    f.append("audio", blob, "audio.webm");
    if (opts.conversation_id) f.append("conversation_id", opts.conversation_id);
    if (opts.language) f.append("language", opts.language);
    if (opts.voice) f.append("voice", opts.voice);
    return apiFetch<VoiceChatResponse>("/v1/voice/chat", { method: "POST", body: f });
  },
  /** Live full-duplex voice: exchange a WebRTC offer for an answer + session + WS ticket. */
  liveOffer(sdp: string, language: string, voiceName?: string): Promise<LiveOfferResponse> {
    return apiFetch<LiveOfferResponse>("/v1/live/offer", {
      method: "POST", body: { sdp, type: "offer", language, ...(voiceName ? { voice: voiceName } : {}) },
    });
  },
  liveIce(session_id: string, candidate: RTCIceCandidateInit | null): Promise<void> {
    return apiFetch<void>("/v1/live/ice", { method: "POST", body: { session_id, candidate } });
  },
};
