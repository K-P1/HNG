from fastapi import APIRouter, Depends, HTTPException, Query, Path
from sqlalchemy.orm import Session
from app.database import get_db
from app import schemas
from app.services import country_service
from fastapi.responses import FileResponse
from typing import Optional, List
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
    return country_service.refresh_countries(db)

@router.get(
    "/",
    response_model=List[schemas.CountryOut],
    summary="List countries",
    description=(
        "Returns countries with optional filtering, sorting, and pagination.\n\n"
        "Filters:\n"
        "- region: case-insensitive partial match; wildcards (%) and (_) supported (e.g., 'eu' → 'Europe')\n"
        "- currency: 3-letter currency code (e.g., 'USD', 'NGN')\n\n"
        "Sorting options (sort): name_asc|name_desc|population_asc|population_desc|gdp_asc|gdp_desc\n\n"
        "Pagination: use limit and offset."
    ),
    response_description="List of countries",
)
def get_all(
    region: Optional[str] = Query(
        default=None,
        description="Filter by region (case-insensitive partial match; wildcards % and _ supported)",
    ),
    currency: Optional[str] = Query(
        default=None,
        description="Filter by currency code (ISO 4217, case-insensitive)",
        min_length=3,
        max_length=10,
    ),
    sort: Optional[str] = Query(
        default=None,
        description=(
            "Sort order: one of name_asc, name_desc, population_asc, population_desc, gdp_asc, gdp_desc"
        ),
    ),
    limit: Optional[int] = Query(
        default=None,
        ge=1,
        le=500,
        description="Maximum number of records to return (1-500)",
    ),
    offset: Optional[int] = Query(
        default=None,
        ge=0,
        description="Number of records to skip before starting to collect the result set",
    ),
    db: Session = Depends(get_db),
    _: None = _rate_limit(settings.RATE_LIMIT_DEFAULT_TIMES, settings.RATE_LIMIT_DEFAULT_SECONDS),
):
    return country_service.list_countries(db, region, currency, sort, limit, offset)

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
    return country_service.get_country_by_name(db, name)

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
    return country_service.delete_country_by_name(db, name)
