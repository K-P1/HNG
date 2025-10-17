from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging
from typing import Any, cast
from .config import settings

try:
    import redis.asyncio as redis
except Exception:
    redis = None

from .routes import router
from . import limiter as limiter_module

logger = logging.getLogger("app")
logging.basicConfig(level=logging.INFO)

REDIS_URL = settings.REDIS_URL
redis_client = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global redis_client
    if redis is None:
        logger.info("redis.asyncio package not available; Redis features disabled")
        redis_client = None
    else:
        try:
            redis_client = redis.from_url(REDIS_URL, decode_responses=True)
            await redis_client.ping()
            logger.info("Connected to Redis at %s", REDIS_URL)
        except Exception:
            redis_client = None
            logger.warning("Failed to connect to Redis at %s — continuing without Redis", REDIS_URL)
    try:
        yield
    finally:
        if redis_client is not None:
            try:
                from typing import Callable, Awaitable, cast

                aclose_attr = getattr(redis_client, "aclose", None)
                if callable(aclose_attr):
                    aclose_async = cast(Callable[[], Awaitable[None]], aclose_attr)
                    await aclose_async()
                else:
                    await redis_client.close()
                logger.info("Closed Redis connection")
            except Exception:
                logger.exception("Error closing Redis connection")


app = FastAPI(lifespan=lifespan)
app.state.limiter = limiter_module.limiter



mw = cast(Any, limiter_module.get_middleware())
app.add_middleware(mw)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)
