from typing import Optional
import httpx
import logging
import asyncio
import random

from .config import settings

logger = logging.getLogger("app.services")

# Config from settings
CAT_FACTS_URL = settings.CAT_FACTS_URL
CAT_FACTS_TIMEOUT = settings.CAT_FACTS_TIMEOUT
CAT_FACTS_MAX_RETRIES = settings.CAT_FACTS_MAX_RETRIES
CAT_FACTS_BACKOFF_FACTOR = settings.CAT_FACTS_BACKOFF_FACTOR
CAT_FACTS_FALLBACK = settings.CAT_FACTS_FALLBACK


def _parse_retry_after(header_value: Optional[str]) -> Optional[float]:
    if not header_value:
        return None
    try:
        return float(header_value)
    except Exception:
        return None


async def fetch_cat_fact(timeout_seconds: Optional[float] = None) -> str:
    timeout_seconds = timeout_seconds or CAT_FACTS_TIMEOUT

    attempt = 0
    while True:
        attempt += 1
        try:
            timeout = httpx.Timeout(timeout_seconds)
            async with httpx.AsyncClient(timeout=timeout) as client:
                resp = await client.get(CAT_FACTS_URL)

                # Any 4xx/5xx will raise and be handled below; treat 429 as retryable.
                if resp.status_code == 429 or 500 <= resp.status_code < 600:
                    resp.raise_for_status()

                resp.raise_for_status()

                payload = resp.json()
                fact = payload.get("fact") if isinstance(payload, dict) else None
                if fact:
                    return fact

                logger.warning("Cat facts API returned unexpected payload: %s", payload)
                return CAT_FACTS_FALLBACK

        except httpx.HTTPStatusError as exc:
            status = getattr(exc.response, "status_code", None)
            ra_header = exc.response.headers.get("Retry-After") if exc.response is not None else None
            ra = _parse_retry_after(ra_header)
            logger.warning("Cat Facts API returned HTTP error: %s", exc)

            # Retry only for 429 or 5xx
            if attempt <= CAT_FACTS_MAX_RETRIES and (status == 429 or (status and 500 <= status < 600)):
                wait_seconds = ra if ra is not None else (CAT_FACTS_BACKOFF_FACTOR * (2 ** (attempt - 1)))
                # jitter +/-20%
                jitter = wait_seconds * 0.2
                wait_seconds = max(0.0, wait_seconds + random.uniform(-jitter, jitter))
                logger.info("Retrying Cat Facts API in %.2f seconds (attempt %d/%d)", wait_seconds, attempt, CAT_FACTS_MAX_RETRIES)
                try:
                    await asyncio.sleep(wait_seconds)
                    continue
                except asyncio.CancelledError:
                    raise

        except httpx.RequestError as exc:
            logger.warning("Request to Cat Facts API failed: %s", exc)
            if attempt <= CAT_FACTS_MAX_RETRIES:
                wait_seconds = CAT_FACTS_BACKOFF_FACTOR * (2 ** (attempt - 1))
                jitter = wait_seconds * 0.2
                wait_seconds = max(0.0, wait_seconds + random.uniform(-jitter, jitter))
                logger.info("Retrying after RequestError in %.2f seconds (attempt %d/%d)", wait_seconds, attempt, CAT_FACTS_MAX_RETRIES)
                await asyncio.sleep(wait_seconds)
                continue

        except Exception as exc:
            logger.exception("Unexpected error fetching cat fact: %s", exc)

        return CAT_FACTS_FALLBACK
