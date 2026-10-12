from app.core.config import Settings, get_settings
from app.core.i18n import recognised_language
from app.providers.base import EmbeddingProvider, LLMProvider, STTProvider, TTSProvider


class ProviderConfigError(ValueError):
    """Provider is misconfigured (missing key/model or unknown provider). Maps to HTTP 503."""


def _require(settings: Settings, **fields: str) -> None:
    for env_name, attr in fields.items():
        if not getattr(settings, attr):
            raise ProviderConfigError(f"{env_name} must be set to use this provider")


def _unknown(kind: str, name: str):
    return ProviderConfigError(f"Unknown {kind} provider: {name!r}")


def get_llm(settings: Settings | None = None, model: str | None = None,
            provider: str | None = None) -> LLMProvider:
    """Build the chat LLM.

    - `llm_provider == "fake"` short-circuits to the fake LLM (tests).
    - A `provider` naming an entry in the multi-provider registry (requesty, ollama, cohere,
      nvidia, aionlabs, huggingface, openrouter) builds a generic OpenAI-compatible client.
    - With no `provider`, the legacy OpenRouter path is used (backwards compatible).
    """
    s = settings or get_settings()
    if s.llm_provider == "fake":
        from app.providers.fakes import FakeLLM
        return FakeLLM()
    if provider:
        from app.providers.registry import PROVIDERS, build_llm
        if provider in PROVIDERS:
            return build_llm(s, provider, model or s.default_llm_model, max_tokens=s.llm_max_tokens)
        raise _unknown("llm", provider)
    if s.llm_provider == "openrouter":
        _require(s, OPENROUTER_API_KEY="openrouter_api_key", LLM_MODEL="llm_model")
        from app.providers.llm_openrouter import OpenRouterLLM
        return OpenRouterLLM(s.openrouter_api_key, (model or s.llm_model), s.openrouter_base_url,
                             max_tokens=s.llm_max_tokens)
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
    if s.stt_provider in ("whisper_local", "local"):
        from app.providers.stt_whisper_local import LocalWhisperSTT
        return LocalWhisperSTT(s.whisper_model_size, s.whisper_device, s.whisper_compute_type)
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


def get_streaming_stt(language: str | None, settings: Settings | None = None):
    """Pick a streaming STT for `language`.

    fake -> FakeStreamingSTT; vad -> always VadSegmentedSTT; deepgram -> vendor for its
    languages (raises if unconfigured), VAD-segmented otherwise; auto (default) -> vendor
    for supported languages when a key is set, else VadSegmentedSTT. Kinyarwanda/unknown
    languages always use VadSegmentedSTT (no word-level vendor support).
    """
    s = settings or get_settings()
    mode = s.streaming_stt_provider
    if mode == "fake":
        from app.providers.streaming_stt import FakeStreamingSTT
        return FakeStreamingSTT()
    if mode not in ("auto", "deepgram", "vad"):
        raise _unknown("streaming stt", mode)
    from app.providers.streaming_stt import StreamingVendorSTT, VadSegmentedSTT
    lang = recognised_language(language)
    supported = {x.strip() for x in s.streaming_stt_languages.split(",") if x.strip()}
    if mode != "vad" and lang is not None and lang in supported:
        if mode == "deepgram" or s.streaming_stt_api_key:
            _require(s, STREAMING_STT_API_KEY="streaming_stt_api_key")
            return StreamingVendorSTT(s.streaming_stt_api_key, s.streaming_stt_model,
                                      s.streaming_stt_url, s.vad_sample_rate,
                                      tuple(sorted(supported)))
    return VadSegmentedSTT(get_stt(s), sample_rate=s.vad_sample_rate)
