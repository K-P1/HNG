from fastapi import APIRouter, Depends, HTTPException, Query, Path
from sqlalchemy.orm import Session
from app.database import get_db
from app import crud, schemas
import app.services.fetch_data as fetch_data
from app.services.image_generator import generate_summary_image
from fastapi.responses import FileResponse
from typing import Optional, List, cast
from datetime import datetime, timezone
from app.config import settings

try:
    from fastapi_limiter.depends import RateLimiter  # type: ignore
except Exception:  # pragma: no cover
    RateLimiter = None  # type: ignore


def _rate_limit(times: int, seconds: int):
    """Return a dependency that enforces a rate limit when Redis is configured; otherwise no-op."""
    if settings.REDIS_URL and RateLimiter is not None:
        return Depends(RateLimiter(times=times, seconds=seconds))

    async def _noop():
        return None

    return Depends(_noop)

router = APIRouter()
VALID_SORTS = {"name_asc","name_desc","population_asc","population_desc","gdp_asc","gdp_desc"}

@router.post(
    "/refresh",
    summary="Refresh country, currency, and exchange data",
    description=(
        "Fetches the latest data from external providers and refreshes the local database. "
        "Also regenerates the summary image for the top 5 GDP countries."
    ),
)
def refresh_countries(
    db: Session = Depends(get_db),
    _: None = _rate_limit(settings.RATE_LIMIT_REFRESH_TIMES, settings.RATE_LIMIT_REFRESH_SECONDS),
):
    success = fetch_data.refresh_data(db)
    if not success:
        source = getattr(fetch_data, "LAST_ERROR_SOURCE", None) or "External API"
        raise HTTPException(
            status_code=503,
            detail={
                "error": "External data source unavailable",
                "details": f"Could not fetch data from {source}",
            },
        )

    # Update global last_refreshed_at meta timestamp on successful refresh
    now_iso = None
    last_dt: Optional[datetime] = None
    try:
        now = datetime.now(timezone.utc)
        crud.set_last_refresh(db, now)
        now_iso = now.isoformat()
        last_dt = now
    except Exception:
        # Non-fatal: if setting meta fails, proceed
        now_iso = None

    countries = crud.get_countries(db)
    top5 = sorted(countries, key=lambda c: c.estimated_gdp or 0, reverse=True)[:5]
    last_ts: Optional[str] = None
    # Prefer global last refresh timestamp; fall back to per-country max if not available
    if now_iso:
        last_ts = now_iso
    else:
        if countries:
            with_ts_any = [c.last_refreshed_at for c in countries if c.last_refreshed_at is not None]
            if with_ts_any:
                with_ts = cast(list[datetime], with_ts_any)
                latest = max(with_ts)
                last_dt = latest
                last_ts = latest.isoformat()

    # Format timestamp for image: "YYYY-MM-DD HH:MM UTC"
    ts_for_image = "(unknown)"
    try:
        dt = last_dt if last_dt else (datetime.fromisoformat(last_ts) if last_ts else None)
        if dt is not None:
            ts_for_image = dt.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    except Exception:
        # If parsing fails, fall back to the raw string with UTC label if it clearly indicates UTC
        ts_for_image = (last_ts + " UTC") if last_ts else "(unknown)"

    generate_summary_image(top5, len(countries), ts_for_image)

    return {"message": "Data refreshed successfully"}

@router.get(
    "/",
    response_model=List[schemas.CountryOut],
    summary="List countries",
    description=(
        "Returns countries with optional filtering, sorting, and pagination.\n\n"
        "Filters:\n"
        "- region: case-insensitive exact region match (e.g., 'Europe')\n"
        "- currency: 3-letter currency code (e.g., 'USD', 'NGN')\n\n"
        "Sorting options (sort): name_asc|name_desc|population_asc|population_desc|gdp_asc|gdp_desc\n\n"
        "Pagination: use limit and offset."
    ),
    response_description="List of countries",
)
def get_all(
    region: Optional[str] = Query(
        default=None,
        description="Filter by region (case-insensitive exact match)",
        example="Europe",
    ),
    currency: Optional[str] = Query(
        default=None,
        description="Filter by currency code (ISO 4217, case-insensitive)",
        example="USD",
        min_length=3,
        max_length=10,
    ),
    sort: Optional[str] = Query(
        default=None,
        description=(
            "Sort order: one of name_asc, name_desc, population_asc, population_desc, gdp_asc, gdp_desc"
        ),
        example="population_desc",
    ),
    limit: Optional[int] = Query(
        default=None,
        ge=1,
        le=500,
        description="Maximum number of records to return (1-500)",
        example=50,
    ),
    offset: Optional[int] = Query(
        default=None,
        ge=0,
        description="Number of records to skip before starting to collect the result set",
        example=0,
    ),
    db: Session = Depends(get_db),
    _: None = _rate_limit(settings.RATE_LIMIT_DEFAULT_TIMES, settings.RATE_LIMIT_DEFAULT_SECONDS),
):
    # Validate sort parameter strictly per spec
    if sort is not None and sort not in VALID_SORTS:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "Validation failed",
                "details": {"sort": "invalid value; must be one of: " + ", ".join(sorted(VALID_SORTS))},
            },
        )
    return crud.get_countries(db, region, currency, sort, limit, offset)

@router.get(
    "/image",
    summary="Get generated summary image",
    description=(
        "Returns a PNG image summarizing dataset insights (top 5 GDP countries, total count, last refresh time)."
    ),
)
def get_image(
    _: None = _rate_limit(settings.RATE_LIMIT_IMAGE_TIMES, settings.RATE_LIMIT_IMAGE_SECONDS),
):
    img_path = settings.BASE_DIR / "cache" / "summary.png"
    if not img_path.exists():
        raise HTTPException(status_code=404, detail="Summary image not found")
    return FileResponse(str(img_path), media_type="image/png")

@router.get(
    "/{name}",
    response_model=schemas.CountryOut,
    summary="Get country by name",
    description="Case-insensitive exact country name match.",
)
def get_one(
    name: str = Path(..., description="Exact country name", example="Nigeria"),
    db: Session = Depends(get_db),
    _: None = _rate_limit(settings.RATE_LIMIT_DEFAULT_TIMES, settings.RATE_LIMIT_DEFAULT_SECONDS),
):
    country = crud.get_country(db, name)
    if not country:
        raise HTTPException(status_code=404, detail="Country not found")
    return country

@router.delete(
    "/{name}",
    summary="Delete a country by name",
    description="Deletes a country if it exists. Primarily for maintenance/testing.",
)
def delete_country(
    name: str = Path(..., description="Exact country name", example="Nigeria"),
    db: Session = Depends(get_db),
    _: None = _rate_limit(settings.RATE_LIMIT_DEFAULT_TIMES, settings.RATE_LIMIT_DEFAULT_SECONDS),
):
    if not crud.delete_country(db, name):
        raise HTTPException(status_code=404, detail="Country not found")
    return {"message": "Deleted successfully"}
