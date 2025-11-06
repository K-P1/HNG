# main.py
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from app import database
from app.routes import router

# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,  # switch to DEBUG only when diagnosing
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger("main")
logger.info("Application starting...")


# ---------------------------------------------------------------------------
# App lifespan (startup/shutdown)
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handle startup and shutdown tasks."""
    logger.info("Startup: initializing database...")
    try:
        await database.init_db_async()
        dsn = database.get_database_dsn()
        logger.info("Connected to database: %s", dsn)
    except Exception as e:
        logger.critical("Database initialization failed: %s", e)
        raise  # fail fast — app should not start without DB

    # Start reminder scheduler only in async mode (reminders require push notifications)
    import os
    async_enabled = os.getenv("A2A_ASYNC_ENABLED", "").lower() in ("true", "1", "yes")
    if async_enabled:
        logger.info("Startup: starting reminder scheduler...")
        try:
            from app.features.reminders import start_reminder_scheduler
            await start_reminder_scheduler()
            logger.info("Reminder scheduler started successfully")
        except Exception as e:
            logger.error("Failed to start reminder scheduler: %s", e)
    else:
        logger.info("Reminder scheduler disabled (A2A_ASYNC_ENABLED not set)")

    yield  # app runs during this block

    # Cleanup
    import os
    async_enabled = os.getenv("A2A_ASYNC_ENABLED", "").lower() in ("true", "1", "yes")
    if async_enabled:
        logger.info("Shutdown: stopping reminder scheduler...")
        try:
            from app.features.reminders import stop_reminder_scheduler
            await stop_reminder_scheduler()
            logger.info("Reminder scheduler stopped")
        except Exception as e:
            logger.error("Error stopping reminder scheduler: %s", e)
    
    logger.info("Shutdown: closing database connection pool...")
    try:
        await database.shutdown_db_async()
        logger.info("Cleanup complete.")
    except Exception as e:
        logger.error("Error during shutdown cleanup: %s", e)


# ---------------------------------------------------------------------------
# FastAPI Application
# ---------------------------------------------------------------------------
app = FastAPI(
    title="Reflective Assistant - Telex Agent",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Base Routes
# ---------------------------------------------------------------------------

@app.get("/", tags=["Health"])
async def root():
    """Basic health check to verify the service is running."""
    return {"status": "ok", "message": "Reflective Assistant is running."}


# Include your main feature routes
app.include_router(router)
