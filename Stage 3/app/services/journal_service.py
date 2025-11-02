import logging
from typing import Optional, List
from app import crud
from app.services import llm_service

logger = logging.getLogger("services.journal")


async def create_journal(user_id: str, entry: str, summary: Optional[str] = None, sentiment: Optional[str] = None):
    if not summary and not sentiment:
        try:
            sentiment, summary = await llm_service.analyze_entry(entry)
        except Exception:
            sentiment, summary = None, None
    return await crud.create_journal(user_id, entry, summary=summary, sentiment=sentiment)


async def list_journals(user_id: str, limit: int = 20) -> List:
    return await crud.get_journals(user_id, limit)


async def update_journal(journal_id: int, **kwargs):
    return await crud.update_journal(journal_id, **kwargs)


async def delete_journal(journal_id: int):
    return await crud.delete_journal(journal_id)
