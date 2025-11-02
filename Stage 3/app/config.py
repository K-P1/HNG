from __future__ import annotations

from functools import lru_cache
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # App environment
    env: str = Field(default="development", alias="ENV")
    debug: bool = Field(default=False, alias="DEBUG")

    # Database
    database_url: str = Field(default="sqlite+aiosqlite:///./dev.db", alias="DATABASE_URL")

    # LLM provider settings
    llm_provider: str = Field(default="groq", alias="LLM_PROVIDER")
    groq_api_key: Optional[str] = Field(default=None, alias="GROQ_API_KEY")
    groq_model: str = Field(default="llama-3.3-70b-versatile", alias="GROQ_MODEL")

    # Agent naming
    a2a_agent_name: str = Field(default="Raven", alias="A2A_AGENT_NAME")

    # Async configuration for A2A handling (see .env.example for modes)
    # Unset → honor request.configuration.blocking
    # false/0/no → force synchronous
    # true/1/yes → prefer async with push_url (unless blocking: true)
    a2a_async_enabled: Optional[str] = Field(default=None, alias="A2A_ASYNC_ENABLED")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
