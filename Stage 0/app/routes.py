from fastapi import APIRouter, Request
from typing import Any
from .schemas import ResponseModel, UserModel
from .services import fetch_cat_fact
from .config import settings
from .limiter import get_rate_limit_decorator
import logging

router = APIRouter()
logger = logging.getLogger("app.routes")


async def _get_client_ip(request: Request) -> str:
    xff = request.headers.get("x-forwarded-for")
    if xff:
        return xff.split(",")[0].strip()
    if request.client:
        return request.client.host
    return "unknown"


@router.get("/me", response_model=ResponseModel)
@get_rate_limit_decorator()
async def me(request: Request) -> "ResponseModel":
    client_ip = await _get_client_ip(request)
    fact = await fetch_cat_fact()

    user = UserModel(email=settings.USER_EMAIL, name=settings.USER_NAME, stack=settings.USER_STACK)
    response = ResponseModel(user=user, fact=fact)

    if fact and fact.startswith("Could not"):
        logger.warning("/me served fallback fact for %s", client_ip)
    else:
        logger.info("/me served for %s", client_ip)

    return response
