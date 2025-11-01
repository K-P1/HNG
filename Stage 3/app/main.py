import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from app import database
from app.routes import router

# Logging setup
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s %(levelname)s [%(name)s] %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('app.log', mode='a', encoding='utf-8')
    ]
)
logger = logging.getLogger("main")
logger.info("Logging is set up. Application starting...")


@asynccontextmanager
async def lifespan(app):
    logger.info("App startup: initializing database.")
    await database.init_db_async()
    yield
    # Dispose connections before the event loop ends to avoid noisy cleanup warnings
    try:
        await database.shutdown_db_async()
    finally:
        logger.info("App shutdown: cleanup complete.")

app = FastAPI(title="Reflective Assistant - Telex Agent", lifespan=lifespan)

# Allow cross-origin calls (useful during Telex/webhook testing)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(router)
