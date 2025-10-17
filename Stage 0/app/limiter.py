import logging
from typing import Any, List
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.middleware import SlowAPIMiddleware
from .config import settings

logger = logging.getLogger("app.limiter")


def create_limiter() -> Limiter:
    try:
        default_limit = f"{settings.RATE_LIMIT} per {settings.RATE_LIMIT_WINDOW} seconds"
        return Limiter(key_func=get_remote_address, default_limits=[default_limit])
    except Exception:
        logger.exception("Failed to create slowapi Limiter")
        raise


limiter = create_limiter()


def get_rate_limit_decorator(limit: str | None = None) -> Any:
    if limit:
        return limiter.limit(limit)
    default_limit = f"{settings.RATE_LIMIT} per {settings.RATE_LIMIT_WINDOW} seconds"
    return limiter.limit(default_limit)


def get_middleware() -> Any:
    return SlowAPIMiddleware
