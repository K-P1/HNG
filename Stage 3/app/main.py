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
        logging.FileHandler("app.log", mode="a", encoding="utf-8"),
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

    yield  # app runs during this block

    # Cleanup
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
