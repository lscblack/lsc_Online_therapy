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
    # Provider selectors: llm/stt/tts = fake|openrouter|digitalumuganda(stt/tts); embedding = fake|e5
    llm_provider: str = "openrouter"
    embedding_provider: str = "e5"
    stt_provider: str = "openrouter"
    tts_provider: str = "openrouter"
    encryption_key: str = ""
    jwt_secret: str = ""
    retention_days: int = 30
    retrieval_min_score: float = 0.3


@lru_cache
def get_settings() -> Settings:
    return Settings()
