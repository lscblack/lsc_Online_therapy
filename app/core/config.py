from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str
    openrouter_api_key: str
    llm_model: str
    embedding_model: str = "intfloat/multilingual-e5-base"
    encryption_key: str
    jwt_secret: str
    retention_days: int = 30
    retrieval_min_score: float = 0.3


@lru_cache
def get_settings() -> Settings:
    return Settings()
