import logging
import os
import atexit
import asyncio
from typing import Any
from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import create_async_engine, AsyncEngine, async_sessionmaker
from sqlalchemy.orm import declarative_base
from sqlalchemy.pool import NullPool

logger = logging.getLogger("database")

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

# Detect testing mode to avoid cross-event-loop issues with aiomysql when tests use asyncio.run repeatedly
IS_TESTING = bool(os.getenv("PYTEST_CURRENT_TEST")) or os.getenv("APP_ENV") in {"test", "testing"} or os.getenv("ENV") in {"test", "testing"}

if DATABASE_URL:
    # Normalize drivers
    if "+pymysql" in DATABASE_URL:
        DATABASE_URL = DATABASE_URL.replace("+pymysql", "+aiomysql")
    if DATABASE_URL.startswith("sqlite://") and "+aiosqlite" not in DATABASE_URL:
        DATABASE_URL = DATABASE_URL.replace("sqlite://", "sqlite+aiosqlite://", 1)
    # For tests, force sqlite to prevent event loop/aiomysql transport issues
    if IS_TESTING and DATABASE_URL.startswith("mysql+"):
        logger.warning("Detected test environment; overriding MySQL DATABASE_URL with sqlite+aiosqlite for stability.")
        DATABASE_URL = "sqlite+aiosqlite:///./test.db"
else:
    logger.warning("DATABASE_URL not set; falling back to local sqlite+aiosqlite for development/tests.")
    DATABASE_URL = "sqlite+aiosqlite:///./dev.db"

try:
    is_mysql_async = DATABASE_URL.startswith("mysql+aiomysql")
    engine_kwargs: dict[str, Any] = {
        "future": True,
        # be resilient to dropped conns in long-lived processes
        "pool_pre_ping": True,
    }
    # Avoid pooled cross-loop connections with aiomysql (fixes 'Event loop is closed' on GC/shutdown)
    if is_mysql_async:
        engine_kwargs["poolclass"] = NullPool
    async_engine: AsyncEngine = create_async_engine(DATABASE_URL, **engine_kwargs)
except Exception as e:
    logger.warning("Failed to create async engine with DATABASE_URL=%s: %s", DATABASE_URL, e)
    logger.warning("Falling back to sqlite in-memory async engine for safety.")
    async_engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)

AsyncSessionLocal = async_sessionmaker(bind=async_engine, expire_on_commit=False)
Base = declarative_base()


async def init_db_async():
    """Create database tables asynchronously (call on startup)."""
    try:
        from app.models import models

        async with async_engine.begin() as conn:
            await conn.run_sync(models.Base.metadata.create_all)
        logger.info("Database tables created successfully.")
    except Exception as e:
        logger.error(f"Failed to create database tables: {e}")

async def shutdown_db_async():
    """Dispose the async engine on shutdown to close pools cleanly."""
    try:
        await async_engine.dispose()
        logger.info("Database engine disposed successfully.")
    except Exception as e:
        logger.warning("Error disposing database engine: %s", e)


# Safety net: ensure connections are closed before interpreter exit even if app shutdown hooks aren't called
def _dispose_engine_at_exit():
    try:
        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(async_engine.dispose())
        finally:
            loop.close()
    except Exception:
        # Avoid noisy logs on interpreter shutdown
        pass

atexit.register(_dispose_engine_at_exit)

