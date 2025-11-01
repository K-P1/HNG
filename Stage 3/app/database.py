import logging
import os
from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import create_async_engine, AsyncEngine, async_sessionmaker
from sqlalchemy.orm import declarative_base

logger = logging.getLogger("database")

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
if DATABASE_URL:
    if "+pymysql" in DATABASE_URL:
        DATABASE_URL = DATABASE_URL.replace("+pymysql", "+aiomysql")
    if DATABASE_URL.startswith("sqlite://") and "+aiosqlite" not in DATABASE_URL:
        DATABASE_URL = DATABASE_URL.replace("sqlite://", "sqlite+aiosqlite://", 1)
else:
    logger.warning("DATABASE_URL not set; falling back to local sqlite+aiosqlite for development/tests.")
    DATABASE_URL = "sqlite+aiosqlite:///./dev.db"

try:
    async_engine: AsyncEngine = create_async_engine(DATABASE_URL, future=True)
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


def init_db():
    """Synchronous wrapper for creating DB tables; uses asyncio.run()."""
    import asyncio

    try:
        asyncio.run(init_db_async())
    except Exception as e:
        logger.error("Failed to run init_db_async(): %s", e)
