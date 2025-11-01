import logging
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from dotenv import load_dotenv

# Logging setup for database module
logger = logging.getLogger("database")

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL environment variable not set")

# Engine configuration
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,   # Checks connection before using it
    pool_recycle=280,     # Recycles stale connections
    pool_size=5,          # Adjust for your plan limits
    max_overflow=10,      # Temporary overflow connections
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def init_db():
    """Create database tables (call on startup)."""
    try:
        from app.models import models
        models.Base.metadata.create_all(bind=engine)
        logger.info("Database tables created successfully.")
    except Exception as e:
        logger.error(f"Failed to create database tables: {e}")
