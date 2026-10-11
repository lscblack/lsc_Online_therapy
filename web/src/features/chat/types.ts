import type { ChatResponse } from "../../api/types";

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  text: string;
  status: "streaming" | "done" | "error";
  meta?: ChatResponse;
  /** The user text that produced this assistant message (for retry). */
  userText?: string;
}
