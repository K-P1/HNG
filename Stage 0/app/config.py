from pydantic import EmailStr
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    USER_EMAIL: EmailStr = "you@example.com"
    USER_NAME: str = "Your Name"
    USER_STACK: str = "Python/FastAPI"

    CAT_FACTS_URL: str = "https://catfact.ninja/fact"
    CAT_FACTS_TIMEOUT: float = 2.0
    CAT_FACTS_MAX_RETRIES: int = 3
    CAT_FACTS_BACKOFF_FACTOR: float = 0.5
    CAT_FACTS_FALLBACK: str = "Could not fetch a cat fact at this time."

    REDIS_URL: str = "redis://localhost:6379/0"
    RATE_LIMIT: int = 5
    RATE_LIMIT_WINDOW: int = 60

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }

settings = Settings()
