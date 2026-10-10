from app.core.config import Settings, get_settings
from app.providers.base import EmbeddingProvider, LLMProvider, STTProvider, TTSProvider


def _require(settings: Settings, **fields: str) -> None:
    for env_name, attr in fields.items():
        if not getattr(settings, attr):
            raise ValueError(f"{env_name} must be set to use this provider")


def _unknown(kind: str, name: str):
    return ValueError(f"Unknown {kind} provider: {name!r}")


def get_llm(settings: Settings | None = None) -> LLMProvider:
    s = settings or get_settings()
    if s.llm_provider == "fake":
        from app.providers.fakes import FakeLLM
        return FakeLLM()
    if s.llm_provider == "openrouter":
        _require(s, OPENROUTER_API_KEY="openrouter_api_key", LLM_MODEL="llm_model")
        from app.providers.llm_openrouter import OpenRouterLLM
        return OpenRouterLLM(s.openrouter_api_key, s.llm_model, s.openrouter_base_url)
    raise _unknown("llm", s.llm_provider)


def get_embeddings(settings: Settings | None = None) -> EmbeddingProvider:
    s = settings or get_settings()
    if s.embedding_provider == "fake":
        from app.providers.fakes import FakeEmbeddings
        return FakeEmbeddings()
    if s.embedding_provider == "e5":
        _require(s, EMBEDDING_MODEL="embedding_model")
        from app.providers.embeddings_e5 import LocalE5Embeddings
        return LocalE5Embeddings(s.embedding_model)
    raise _unknown("embedding", s.embedding_provider)


def get_stt(settings: Settings | None = None) -> STTProvider:
    s = settings or get_settings()
    if s.stt_provider == "fake":
        from app.providers.fakes import FakeSTT
        return FakeSTT()
    if s.stt_provider == "openrouter":
        _require(s, OPENROUTER_API_KEY="openrouter_api_key")
        from app.providers.stt_openrouter import OpenRouterWhisperSTT
        return OpenRouterWhisperSTT(s.openrouter_api_key, s.stt_model, s.openrouter_base_url)
    if s.stt_provider == "digitalumuganda":
        from app.providers.stubs_digitalumuganda import DigitalUmugandaSTT
        return DigitalUmugandaSTT()
    raise _unknown("stt", s.stt_provider)


def get_tts(settings: Settings | None = None) -> TTSProvider:
    s = settings or get_settings()
    if s.tts_provider == "fake":
        from app.providers.fakes import FakeTTS
        return FakeTTS()
    if s.tts_provider == "openrouter":
        _require(s, OPENROUTER_API_KEY="openrouter_api_key")
        from app.providers.tts_openrouter import OpenRouterTTS
        return OpenRouterTTS(s.openrouter_api_key, s.tts_model, s.openrouter_base_url)
    if s.tts_provider == "digitalumuganda":
        from app.providers.stubs_digitalumuganda import DigitalUmugandaTTS
        return DigitalUmugandaTTS()
    raise _unknown("tts", s.tts_provider)
