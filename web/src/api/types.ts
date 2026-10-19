/** Types matching the backend OpenAPI (app/schemas). */
export interface TokenPair { access_token: string; refresh_token: string; token_type?: string }
export interface AnonSession extends TokenPair { anon_id: string }
export interface UpgradeResponse { is_upgraded: boolean }

export type AgeBand = "under15" | "15_17" | "18_19" | "20_24" | "25_plus" | "undisclosed";
export interface Profile {
  nickname: string | null; age_band: AgeBand; gender: string | null; pronouns: string | null;
  tone_pref: string | null; interests: string[]; sensitive_context?: string | null;
  consent: Record<string, unknown>; updated_at: string | null;
}
export interface ProfileUpdate {
  nickname?: string | null; age_band?: AgeBand | null; gender?: string | null;
  pronouns?: string | null; tone_pref?: string | null; interests?: string[] | null;
  sensitive_context?: string | null;
}

export type Citation = Record<string, unknown>;
export type SafetyFlags = Record<string, unknown>;
export interface ChatRequest { message: string; conversation_id?: string | null; language?: string | null }
export interface ChatResponse {
  answer: string; citations: Citation[]; conversation_id: string; safety_flags: SafetyFlags; language: string;
}
export interface VoiceChatResponse extends ChatResponse {
  transcript: string; audio_base64: string; audio_mime: string; tts_available: boolean;
}
export interface TranscribeResponse { text: string; language: string | null }
export interface VoiceChatOptions { conversation_id?: string | null; language?: string | null; voice?: string | null }
export interface LiveOfferResponse {
  session_id: string; type: string; sdp: string; ice_servers: RTCIceServer[]; ws_ticket: string;
}

export type DocStatus = "uploaded" | "processing" | "indexed" | "failed";
export type ReviewStatus = "pending" | "approved" | "rejected";
export interface Document {
  id: string; title: string; source_filename: string | null; language: string | null;
  topic_tags: string[]; status: DocStatus; review_status: ReviewStatus; review_notes: string | null;
  version: number; checksum: string | null; created_at: string; indexed_at: string | null;
}
export interface Chunk { chunk_index: number; content: string; token_count: number; language: string | null }
export type UserRole = "user" | "reviewer" | "admin";
export interface User {
  id: string; email: string | null; role: UserRole; is_upgraded: boolean; locale: string;
  disabled: boolean; created_at: string; last_seen_at: string | null;
}
export interface AuditEntry {
  id: string; actor_id: string | null; action: string; target: string | null;
  metadata: unknown; at: string;
}

export interface ProviderInfo {
  name: string; label: string; tier: string; note: string;
  enabled: boolean; local: boolean; models: string[];
}
export interface ModelConfig {
  active_provider: string; active_model: string; is_override: boolean; providers: ProviderInfo[];
}
export interface ProviderModels { provider: string; models: string[] }
export interface SystemInfo {
  stt_provider: string; whisper_model: string; stt_device: string;
  cuda_available: boolean; cuda_devices: number;
  /** Jev decision layer (triage + rerank). Optional: older backends omit it. */
  jev?: { configured: boolean; model: string; triage: boolean; rerank: boolean };
}
export interface TestModelResult {
  provider: string; model: string; ok: boolean; latency_ms: number; sample: string; error: string | null;
}

export interface ErrorEnvelope { error: { code: string; message: string; details?: unknown } }

/** Result of streaming chat: assembled text plus the final `done` metadata when provided. */
export interface StreamResult { message: string; meta: ChatResponse | null }
