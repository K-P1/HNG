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

    # Reminder settings
    reminder_check_interval_minutes: int = Field(default=1, alias="REMINDER_CHECK_INTERVAL_MINUTES")
    reminder_advance_hours: str = Field(default="24,1", alias="REMINDER_ADVANCE_HOURS")  # Comma-separated: 24h, 1h before
    reminder_quiet_hours_start: int = Field(default=22, alias="REMINDER_QUIET_HOURS_START")  # 10pm
    reminder_quiet_hours_end: int = Field(default=8, alias="REMINDER_QUIET_HOURS_END")  # 8am
    reminder_max_overdue_reminders: int = Field(default=5, alias="REMINDER_MAX_OVERDUE_REMINDERS")
    reminder_overdue_interval_hours: int = Field(default=24, alias="REMINDER_OVERDUE_INTERVAL_HOURS")  # Remind every 24h when overdue

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
