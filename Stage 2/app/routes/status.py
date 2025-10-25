from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Country
from app import crud
from sqlalchemy import func
from app.config import settings

try:
    from fastapi_limiter.depends import RateLimiter  # type: ignore
except Exception:  # pragma: no cover
    RateLimiter = None  # type: ignore


def _rate_limit(times: int, seconds: int):
    if settings.REDIS_URL and RateLimiter is not None:
        return Depends(RateLimiter(times=times, seconds=seconds))

    async def _noop():
        return None

    return Depends(_noop)

router = APIRouter()

@router.get(
    "/",
    summary="API/data status",
    description="Returns the number of countries stored and the timestamp of the last refresh.",
)
def get_status(
    db: Session = Depends(get_db),
    _: None = _rate_limit(settings.RATE_LIMIT_DEFAULT_TIMES, settings.RATE_LIMIT_DEFAULT_SECONDS),
):
    total = db.query(func.count(Country.id)).scalar()
    last = crud.get_last_refresh(db) or db.query(func.max(Country.last_refreshed_at)).scalar()
    return {
        "total_countries": total or 0,
        "last_refreshed_at": last
    }
