from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from app.routes import countries, status
from app.database import Base, engine
from app.logging import init_logging, RequestLoggingMiddleware, setup_query_logging
import logging
from app.config import settings
from contextlib import asynccontextmanager

try:
    from redis.asyncio import Redis  # type: ignore
    from fastapi_limiter import FastAPILimiter  # type: ignore
except Exception:  # pragma: no cover
    Redis = None  # type: ignore
    FastAPILimiter = None  # type: ignore

Base.metadata.create_all(bind=engine)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Initialize rate limiter if Redis is configured and available
    if settings.REDIS_URL and Redis is not None and FastAPILimiter is not None:
        try:
            redis = Redis.from_url(settings.REDIS_URL, encoding="utf-8", decode_responses=True)
            await FastAPILimiter.init(redis)
            app.state.rate_limiting_enabled = True
            logging.getLogger("country_api").info("Rate limiting enabled via Redis at %s", settings.REDIS_URL)
        except Exception:
            app.state.rate_limiting_enabled = False
            logging.getLogger("country_api").warning(
                "Failed to initialize Redis rate limiter; continuing without limits", exc_info=True
            )
    else:
        app.state.rate_limiting_enabled = False
        logging.getLogger("country_api").info("Rate limiting not enabled; REDIS_URL not set or Redis not available")
    try:
        yield
    finally:
        pass


app = FastAPI(
    title="Country Currency & Exchange API",
    version="1.0.0",
    description=(
        "REST API to explore countries, currencies, population, and simple GDP estimates.\n\n"
        "Features:\n"
        "- Filter by region and currency\n"
        "- Sort by name, population, or estimated GDP\n"
        "- Lightweight status and a generated summary image\n\n"
        "Rate limiting can be enabled via Redis (set REDIS_URL)."
    ),
    contact={
        "name": "HNG Project",
        "url": "https://github.com/K-P1/HNG",
    },
    lifespan=lifespan,
)

# Initialize logging and middleware
init_logging()
app.add_middleware(RequestLoggingMiddleware)
setup_query_logging(engine)

app.include_router(countries.router, prefix="/countries", tags=["Countries"])
app.include_router(status.router, prefix="/status", tags=["Status"])

@app.get("/")
def root():
    return {"message": "Country Currency & Exchange API running. Visit /docs for API documentation."}

# -------------------------------
# Unified error response handlers
# -------------------------------
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    logging.getLogger("country_api").error(
        "HTTPException: %s %s -> %s | detail=%s",
        request.method,
        request.url.path,
        exc.status_code,
        exc.detail,
        exc_info=True,
    )
    body = {"error": exc.detail if isinstance(exc.detail, str) else "Error"}
    if isinstance(exc.detail, dict):
        body = {
            "error": exc.detail.get("error") or "Error",
            "details": exc.detail.get("details"),
        }
    return JSONResponse(status_code=exc.status_code, content=body)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    logging.getLogger("country_api").error(
        "ValidationError: %s %s | errors=%s",
        request.method,
        request.url.path,
        exc.errors(),
        exc_info=False,
    )
    return JSONResponse(
        status_code=400,
        content={
            "error": "Validation failed",
            "details": exc.errors(),
        },
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logging.getLogger("country_api").exception(
        "Unhandled exception: %s %s",
        request.method,
        request.url.path,
    )
    return JSONResponse(status_code=500, content={"error": "Internal server error"})
