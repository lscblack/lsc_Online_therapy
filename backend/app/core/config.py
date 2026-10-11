from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str
    # Not used until later tasks (which must validate non-empty); empty keeps app importable.
    openrouter_api_key: str = ""
    llm_model: str = ""
    embedding_model: str = "intfloat/multilingual-e5-base"
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    stt_model: str = "openai/whisper-1"
    tts_model: str = "openai/tts-1"
    # Default cap on generated tokens per LLM reply. Required by OpenRouter credit checks:
    # with no cap it assumes the model's max context (e.g. 65536) and rejects the request as
    # unaffordable even when a normal-length answer is well within balance. Per-call opts override.
    llm_max_tokens: int = 1024
    # Additional OpenAI-compatible LLM providers (optional; enabled only when the key is set).
    requesty_api_key: str = ""
    nvidia_api_key: str = ""
    cohere_api_key: str = ""
    aionlabs_api_key: str = ""
    hf_api_key: str = ""
    ollama_base_url: str = "http://127.0.0.1:11434/v1"
    # Default active LLM when no admin override is stored (provider name from the registry + model id).
    default_llm_provider: str = "requesty"
    default_llm_model: str = "google/gemma-4-31b-it"
    # Provider selectors: llm/stt/tts = fake|openrouter|digitalumuganda(stt/tts); embedding = fake|e5
    # llm_provider "fake" short-circuits to the fake LLM (tests); any other value uses real providers.
    llm_provider: str = "openrouter"
    embedding_provider: str = "e5"
    stt_provider: str = "openrouter"
    tts_provider: str = "openrouter"
    # Browser origins allowed by CORS (JSON list in env, e.g. CORS_ORIGINS='["https://app.example"]').
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]
    encryption_key: str = ""
    # Optional first-admin bootstrap, applied once on startup if the account does not exist.
    # Leave empty to disable (the CLI `create_admin` is the alternative). Set both to enable.
    default_admin_email: str = ""
    default_admin_password: str = ""
    jwt_secret: str = ""
    jwt_algorithm: str = "HS256"
    access_token_ttl_min: int = 15
    refresh_token_ttl_days: int = 30
    retention_days: int = 30
    retrieval_min_score: float = 0.3
    storage_dir: str = "./var/uploads"
    # In-process rate limits (requests/minute; <=0 disables). Not shared across workers.
    # Comma-separated proxy IPs/CIDRs whose X-Forwarded-For is trusted for the limiter's client IP.
    # Empty (default) = ignore the header and use the socket peer.
    trusted_proxies: str = ""
    rate_limit_enabled: bool = True
    rate_limit_auth_per_min: int = 10   # per IP: /identity/recover, /admin/login
    rate_limit_chat_per_min: int = 30   # per identity (token) else IP: chat + voice

    # Realtime voice: streaming STT + VAD. streaming_stt_provider = auto|deepgram|vad|fake
    # (auto: vendor for English when configured, else VAD-segmented batch STT).
    streaming_stt_provider: str = "auto"
    streaming_stt_api_key: str = ""
    streaming_stt_model: str = "nova-2"
    streaming_stt_url: str = "wss://api.deepgram.com/v1/listen"
    streaming_stt_languages: str = "en"  # comma-separated codes the vendor handles
    vad_backend: str = "auto"  # auto|silero|webrtc|energy
    vad_sample_rate: int = 16000  # PCM16 mono
    vad_frame_ms: int = 20
    vad_silence_ms: int = 700  # trailing silence that ends an utterance
    vad_min_speech_ms: int = 200  # shorter bursts are discarded as noise
    vad_aggressiveness: int = 2  # webrtcvad 0-3
    vad_energy_threshold: int = 500  # RMS for the energy fallback
    vad_silero_threshold: float = 0.5

    # Realtime voice: WebRTC ICE. TURN is enabled only when turn_secret is set
    # (must equal coturn's static-auth-secret); otherwise STUN-only.
    stun_url: str = "stun:stun.l.google.com:19302"
    turn_url: str = "turn:localhost:3478"
    turn_secret: str = ""
    turn_ttl: int = 3600  # seconds of validity for ephemeral TURN credentials

    # Realtime voice: LiveSession barge-in. Speech within `grace` of agent speech start is
    # ignored (echo/onset); `min_speech` of sustained user speech triggers barge-in; a crisis
    # answer always plays at least `crisis_min_play` before barge-in is honored.
    realtime_barge_in_grace_ms: int = 300
    realtime_barge_in_min_speech_ms: int = 60
    realtime_crisis_min_play_ms: int = 4000
    # Realtime voice: max concurrent live sessions per identity (offer beyond it -> 429).
    realtime_max_sessions_per_user: int = 2
    # Realtime voice: reaper deadlines (seconds). Idle = no WS/ICE/feed activity; max = hard
    # session length; attach grace = time allowed between /offer and the control WS attaching.
    realtime_max_session_seconds: int = 900
    realtime_idle_seconds: int = 120
    realtime_ws_attach_grace_seconds: int = 30
    realtime_reaper_interval_seconds: float = 5.0


@lru_cache
def get_settings() -> Settings:
    return Settings()
