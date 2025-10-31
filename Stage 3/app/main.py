
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

# Alembic migration sync
from alembic.config import Config
from alembic import command

alembic_cfg = Config("alembic.ini")
# Stamp the DB to head before upgrade (forces sync)
command.stamp(alembic_cfg, "head")
command.upgrade(alembic_cfg, "head")


@asynccontextmanager
async def lifespan(app):
    logger.info("App startup: initializing database.")
    database.init_db()
    yield
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
