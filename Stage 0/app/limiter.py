import logging
from typing import Any
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.middleware import SlowAPIMiddleware

logger = logging.getLogger("app.limiter")


def create_limiter() -> Limiter:
    try:
        from .config import settings

        default_limit = f"{settings.RATE_LIMIT} per {settings.RATE_LIMIT_WINDOW} seconds"
        return Limiter(key_func=get_remote_address, default_limits=[default_limit])
    except Exception:
        logger.exception("Failed to create slowapi Limiter")
        raise


limiter = create_limiter()


def get_rate_limit_decorator(limit: str | None = None, error_message: str | None = None) -> Any:
    if limit:
        return limiter.limit(limit, error_message=error_message)
    from .config import settings

    default_limit = f"{settings.RATE_LIMIT} per {settings.RATE_LIMIT_WINDOW} seconds"
    return limiter.limit(default_limit, error_message=error_message)


def get_middleware() -> Any:
    return SlowAPIMiddleware
