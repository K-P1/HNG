from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.services import country_service
from app.config import settings
from .countries import _rate_limit

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
    return country_service.get_status(db)
