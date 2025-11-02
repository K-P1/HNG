import os
import sys
import asyncio
import logging
import atexit
from sqlalchemy.ext.asyncio import create_async_engine, AsyncEngine, async_sessionmaker
from sqlalchemy.pool import NullPool
from sqlalchemy.orm import declarative_base
from sqlalchemy.engine import make_url
from typing import cast
from dotenv import load_dotenv
from app.config import get_settings

load_dotenv()
logger = logging.getLogger("database")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

_settings = get_settings()
# Detect pytest reliably during collection and execution
_is_pytest = bool(os.getenv("PYTEST_CURRENT_TEST")) or ("pytest" in sys.modules)

# Tests always use SQLite; prod/dev app always uses explicit Postgres URL.
TEST_SQLITE_URL = "sqlite+aiosqlite:///./test.db"
_CURRENT_DB_URL: str | None = None

def _detect_driver(url: str) -> str:
    try:
        return make_url(url).drivername
    except Exception:
        return url.split(":", 1)[0]

# ---------------------------------------------------------------------------
# Engine Setup
# ---------------------------------------------------------------------------

try:
    # Only apply pooling parameters for drivers that support them (e.g., Postgres)
    from typing import Any, Dict

    def _make_engine() -> AsyncEngine:
        # Select fixed URL based on context
        if _is_pytest:
            url = TEST_SQLITE_URL
        else:
            url = str(_settings.database_url or "").strip()
            if not url:
                raise RuntimeError("DATABASE_URL is required for the application and must be Postgres (no fallback).")
            driver = _detect_driver(url)
            if not driver.startswith("postgresql+"):
                raise RuntimeError("Application must use Postgres (postgresql+asyncpg). No SQLite fallback for app.")

        driver = _detect_driver(url)
        engine_kwargs: Dict[str, Any] = {
            "echo": False,
            "future": True,
            "pool_pre_ping": True,
        }
        if driver.startswith("postgresql+"):
            engine_kwargs["pool_size"] = 10
            engine_kwargs["max_overflow"] = 5

        # Tests: no pooling, no pre_ping, avoid asyncpg loop issues entirely
        if _is_pytest:
            engine_kwargs["poolclass"] = NullPool
            engine_kwargs["pool_pre_ping"] = False
            engine_kwargs.pop("pool_size", None)
            engine_kwargs.pop("max_overflow", None)

        # track current URL for DSN rendering
        global _CURRENT_DB_URL
        _CURRENT_DB_URL = url

        return create_async_engine(url, **engine_kwargs)

    async_engine: AsyncEngine = _make_engine()
except Exception as e:
    logger.critical("Failed to initialize async engine: %s", e)
    raise RuntimeError("Database engine initialization failed") from e

AsyncSessionLocal = async_sessionmaker(bind=async_engine, expire_on_commit=False)
_initialized: bool = False
Base = declarative_base()


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

def get_database_dsn(hide_password: bool = True) -> str:
    """Return the configured DB DSN string (Postgres in app, SQLite in tests)."""
    url_str = _CURRENT_DB_URL or ""
    try:
        url = make_url(cast(str, url_str))
        return url.render_as_string(hide_password=hide_password)
    except Exception:
        return url_str


async def init_db_async():
    """Initialize database tables on startup."""
    from app.models import models

    try:
        global _initialized
        if _is_pytest and _initialized:
            # Avoid re-initializing between tests to prevent cross-loop issues
            return
        # In tests, ensure the engine/sessionmaker are tied to the current event loop context.
        if _is_pytest:
            global async_engine, AsyncSessionLocal
            try:
                await async_engine.dispose()
            except Exception:
                pass
            # Recreate the engine using the current env (e.g., TEST_DATABASE_URL)
            async_engine = _make_engine()
            AsyncSessionLocal = async_sessionmaker(bind=async_engine, expire_on_commit=False)

        async with async_engine.begin() as conn:
            await conn.run_sync(models.Base.metadata.create_all)
        logger.info("Database initialized successfully.")
        _initialized = True
    except Exception as e:
        logger.critical("Database initialization failed: %s", e)
        raise RuntimeError("Failed to initialize database") from e


async def shutdown_db_async():
    """Dispose the async engine cleanly."""
    try:
        await async_engine.dispose()
        logger.info("Database connection pool closed.")
    except Exception as e:
        logger.error("Error shutting down database engine: %s", e)
        raise


def _dispose_engine_at_exit():
    """Safety cleanup for interpreter shutdown."""
    try:
        loop = asyncio.new_event_loop()
        loop.run_until_complete(async_engine.dispose())
        loop.close()
    except Exception:
        pass  # swallow shutdown noise


atexit.register(_dispose_engine_at_exit)
