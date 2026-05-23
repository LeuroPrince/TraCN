from functools import lru_cache
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "sqlite:///./tracn.db"
    llm_provider: str = "openai-compatible"
    llm_model: str = "gpt-4o-mini"
    llm_base_url: str = "https://api.openai.com/v1"
    llm_api_key_env_name: str = "OPENAI_API_KEY"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def normalized_llm_base_url(self) -> str:
        return self.llm_base_url.rstrip("/")


@lru_cache
def get_settings() -> Settings:
    return Settings()
