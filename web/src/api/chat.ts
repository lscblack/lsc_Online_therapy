import { apiFetchRaw, apiFetch, ApiError } from "./client";
import { parseSSE } from "./sse";
import type { ChatRequest, ChatResponse, StreamResult } from "./types";

export const chat = {
  send: (req: ChatRequest) => apiFetch<ChatResponse>("/v1/chat", { method: "POST", body: req }),

  /**
   * POST /v1/chat/stream. Backend emits `event: delta` (text chunk) then `event: done`
   * (JSON ChatResponse). Each delta calls onToken; returns the assembled message + done metadata.
   */
  async streamSend(req: ChatRequest, onToken: (t: string) => void, signal?: AbortSignal): Promise<StreamResult> {
    const res = await apiFetchRaw("/v1/chat/stream", {
      method: "POST", body: req, signal, headers: { Accept: "text/event-stream" },
    });
    if (!res.body) throw new ApiError("error", "Empty stream", res.status);
    let message = "";
    let meta: ChatResponse | null = null;
    for await (const ev of parseSSE(res.body)) {
      if (ev.event === "done") {
        try { meta = JSON.parse(ev.data) as ChatResponse; } catch { /* ignore malformed meta */ }
      } else if (ev.event === "delta" || ev.event === "message") {
        message += ev.data;
        onToken(ev.data);
      }
    }
    if (meta && meta.answer) message = meta.answer; // guarded final answer is authoritative
    return { message, meta };
  },
};
