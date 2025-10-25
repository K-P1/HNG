from typing import Optional
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.services import fetch_data
from app.services.image_generator import generate_summary_image
from app.services import crud


VALID_SORTS = {"name_asc", "name_desc", "population_asc", "population_desc", "gdp_asc", "gdp_desc"}


def refresh_countries(db: Session) -> dict:
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

    # Persist last refresh timestamp
    now = datetime.now(timezone.utc)
    try:
        crud.set_last_refresh(db, now)
    except Exception:
        pass

    # Build image data (top 5 by GDP)
    countries = crud.get_countries(db)
    top5 = sorted(countries, key=lambda c: c.estimated_gdp or 0, reverse=True)[:5]

    # Use the refresh timestamp for the image footer (UTC)
    try:
        ts_for_image = now.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    except Exception:
        ts_for_image = "(unknown)"

    generate_summary_image(top5, len(countries), ts_for_image)
    return {"message": "Data refreshed successfully"}


def list_countries(
    db: Session,
    region: Optional[str] = None,
    currency: Optional[str] = None,
    sort: Optional[str] = None,
    limit: Optional[int] = None,
    offset: Optional[int] = None,
) -> list:
    if sort is not None and sort not in VALID_SORTS:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "Validation failed",
                "details": {"sort": "invalid value; must be one of: " + ", ".join(sorted(VALID_SORTS))},
            },
        )
    return crud.get_countries(db, region, currency, sort, limit, offset)


def get_country_by_name(db: Session, name: str):
    country = crud.get_country(db, name)
    if not country:
        raise HTTPException(status_code=404, detail="Country not found")
    return country


def delete_country_by_name(db: Session, name: str) -> dict:
    if not crud.delete_country(db, name):
        raise HTTPException(status_code=404, detail="Country not found")
    return {"message": "Deleted successfully"}


def get_status(db: Session) -> dict:
    from sqlalchemy import func  # local import to avoid hard dependency in route-only context
    from app.models import Country

    total = db.query(func.count(Country.id)).scalar() or 0
    last = crud.get_last_refresh(db) or db.query(func.max(Country.last_refreshed_at)).scalar()
    return {"total_countries": total, "last_refreshed_at": last}
