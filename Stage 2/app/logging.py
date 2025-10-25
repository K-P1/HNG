import importlib.util
import logging
import time
from logging.config import dictConfig

from fastapi import Request
from sqlalchemy import event
from sqlalchemy.engine import Engine
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import settings

# ---------------------------------------------------
# Colorlog Availability Check
# ---------------------------------------------------
COLORLOG_AVAILABLE = importlib.util.find_spec("colorlog") is not None

# ---------------------------------------------------
# Global Logging Level
# ---------------------------------------------------
LOG_LEVEL = settings.LOG_LEVEL.upper()

# ---------------------------------------------------
# Logging Configuration
# ---------------------------------------------------
LOGGING_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "default": {
            "format": "[%(asctime)s] %(levelname)s [%(name)s] in %(module)s: %(message)s",
        },
        "color": (
            {
                "()": "colorlog.ColoredFormatter",
                "format": "%(log_color)s[%(asctime)s] %(levelname)s [%(name)s] in %(module)s: %(message)s",
                "log_colors": {
                    "DEBUG": "cyan",
                    "INFO": "green",
                    "WARNING": "yellow",
                    "ERROR": "red",
                    "CRITICAL": "bold_red",
                },
            }
            if COLORLOG_AVAILABLE
            else {}
        ),
    },
    "handlers": {
        # Console handler (only output target)
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "color" if COLORLOG_AVAILABLE else "default",
            "level": settings.CONSOLE_LOG_LEVEL.upper(),
        },
    },
    "loggers": {
        # Silence uvicorn noise in console
        "uvicorn": {"level": "WARNING"},
        "uvicorn.error": {"level": "WARNING"},
        "uvicorn.access": {"level": "WARNING"},
        # SQLAlchemy logs go to console only
        "sqlalchemy.engine": {
            "level": "WARNING",
            "handlers": ["console"],
            "propagate": False,
        },
        # App-specific logs (console only)
        "country_api": {
            "level": LOG_LEVEL,
            "handlers": ["console"],
            "propagate": False,
        },
        "country_api.request": {
            "level": "INFO",
            "handlers": ["console"],
            "propagate": False,
        },
        "country_api.db": {
            "level": "DEBUG",
            "handlers": ["console"],
            "propagate": False,
        },
    },
    "root": {
        "level": LOG_LEVEL,
        "handlers": ["console"],
    },
}


# ---------------------------------------------------
# Initialize Logging
# ---------------------------------------------------
def init_logging() -> None:
    dictConfig(LOGGING_CONFIG)


# ---------------------------------------------------
# Request Logging Middleware
# ---------------------------------------------------
class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        logger = logging.getLogger("country_api.request")
        start_time = time.time()

        response = await call_next(request)

        duration = (time.time() - start_time) * 1000
        logger.info(
            f"{request.method} {request.url.path} "
            f"→ {response.status_code} ({duration:.2f} ms)"
        )
        return response


# ---------------------------------------------------
# SQLAlchemy Query Timing
# ---------------------------------------------------
SLOW_QUERY_THRESHOLD_MS = 200


def setup_query_logging(engine: Engine):
    logger = logging.getLogger("country_api.db")

    @event.listens_for(engine, "before_cursor_execute")
    def before_cursor_execute(
        conn, cursor, statement, parameters, context, executemany
    ):
        context._query_start_time = time.time()

    @event.listens_for(engine, "after_cursor_execute")
    def after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
        total_time = (time.time() - context._query_start_time) * 1000
        if total_time > SLOW_QUERY_THRESHOLD_MS:
            logger.warning(f"Slow Query ({total_time:.2f} ms): {statement}")
        else:
            logger.debug(f"Query ({total_time:.2f} ms): {statement}")
