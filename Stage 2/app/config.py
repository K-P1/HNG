from pydantic_settings import BaseSettings
from pathlib import Path


class Settings(BaseSettings):
    model_config = {"extra": "ignore", "env_file": ".env"}
    DATABASE_URL: str = "sqlite:///./dev.db"
    PORT: int = 8000
    COUNTRY_API: str = "https://restcountries.com/v2/all?fields=name,capital,region,population,flag,currencies"
    EXCHANGE_API: str = "https://open.er-api.com/v6/latest/USD"

    # Logging configuration used by app.logging
    LOG_LEVEL: str = "INFO"
    CONSOLE_LOG_LEVEL: str = "INFO"

    # Base directory of the project
    BASE_DIR: Path = Path(__file__).resolve().parent.parent

    # Rate limiting / Redis configuration
    # If REDIS_URL is not provided, rate limiting will be disabled gracefully.
    REDIS_URL: str | None = None
    RATE_LIMIT_DEFAULT_TIMES: int = 60
    RATE_LIMIT_DEFAULT_SECONDS: int = 60
    RATE_LIMIT_REFRESH_TIMES: int = 10
    RATE_LIMIT_REFRESH_SECONDS: int = 60
    RATE_LIMIT_IMAGE_TIMES: int = 30
    RATE_LIMIT_IMAGE_SECONDS: int = 60

    

settings = Settings()
