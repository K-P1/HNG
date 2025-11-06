import logging
from datetime import datetime, timezone
from typing import Optional, List, Iterable, Dict, Any
from sqlalchemy import select, func, desc
from app.database import AsyncSessionLocal
from app.models import models as db

logger = logging.getLogger("crud")


# --- Generic DB helpers ------------------------------------------------------

async def _get_or_none(session, model, id_):
    obj = await session.get(model, id_)
    if not obj:
        logger.warning("%s with id=%s not found.", model.__name__, id_)
    return obj


async def _commit_refresh(session, obj):
    await session.commit()
    await session.refresh(obj)
    return obj


# --- Task Operations ---------------------------------------------------------

async def create_task(
    user_id: str, 
    description: str, 
    due_date: Optional[datetime] = None,
    reminder_time: Optional[datetime] = None,
    reminder_enabled: bool = True
) -> db.Task:
    async with AsyncSessionLocal() as dbs:
        task = db.Task(
            user_id=user_id, 
            description=description, 
            due_date=due_date,
            reminder_time=reminder_time,
            reminder_enabled=reminder_enabled
        )
        dbs.add(task)
        await _commit_refresh(dbs, task)
        logger.info("Created task %s for user %s", task.id, user_id)
        return task


async def get_tasks(user_id: str) -> List[db.Task]:
    async with AsyncSessionLocal() as dbs:
        result = await dbs.execute(select(db.Task).where(db.Task.user_id == user_id))
        tasks = list(result.scalars())
        logger.info("Fetched %d tasks for user %s", len(tasks), user_id)
        return tasks


async def get_tasks_filtered(
    user_id: str,
    *,
    status: Optional[str] = None,
    limit: Optional[int] = None,
    due_before: Optional[datetime] = None,
    due_after: Optional[datetime] = None,
    query: Optional[str] = None,
    tags: Optional[Iterable[str]] = None,
) -> List[db.Task]:
    tasks = await get_tasks(user_id)

    q = (query or "").strip().lower()
    tag_list = [t.strip().lower() for t in (list(tags) if tags else []) if str(t).strip()]
    st = (status or "").strip().lower() or None

    def _match(t: db.Task) -> bool:
        if st and (t.status or "").lower() != st:
            return False
        if due_before and t.due_date and t.due_date >= due_before:
            return False
        if due_after and t.due_date and t.due_date <= due_after:
            return False
        desc = (t.description or "").lower()
        if q and q not in desc:
            return False
        if tag_list and not all(tag in desc for tag in tag_list):
            return False
        return True

    filtered = [t for t in tasks if _match(t)]
    if isinstance(limit, int) and limit > 0:
        filtered = filtered[: int(limit)]

    logger.info(
        "get_tasks_filtered: user=%s filters={status:%s,limit:%s,dueBefore:%s,dueAfter:%s,query:%s,tags:%s} -> %d result(s)",
        user_id,
        st,
        limit,
        due_before,
        due_after,
        q or None,
        tag_list or None,
        len(filtered),
    )
    return filtered


async def find_tasks_by_description(user_id: str, query: str) -> List[db.Task]:
    query = (query or "").strip().lower()
    if not query:
        return []
    async with AsyncSessionLocal() as dbs:
        stmt = (
            select(db.Task)
            .where(db.Task.user_id == user_id)
            .where(func.lower(db.Task.description).like(f"%{query}%"))
            .order_by(desc(db.Task.created_at))
        )
        result = await dbs.execute(stmt)
        return list(result.scalars())


async def update_task(
    task_id: int,
    *,
    description: Optional[str] = None,
    status: Optional[str] = None,
    due_date: Optional[datetime] = None,
    reminder_time: Optional[datetime] = None,
    reminder_enabled: Optional[bool] = None,
) -> Optional[db.Task]:
    async with AsyncSessionLocal() as dbs:
        task = await _get_or_none(dbs, db.Task, task_id)
        if not task:
            return None
        if description is not None:
            task.description = description
        if status is not None:
            task.status = status
        if due_date is not None:
            task.due_date = due_date
        if reminder_time is not None:
            task.reminder_time = reminder_time
        if reminder_enabled is not None:
            task.reminder_enabled = reminder_enabled
        await _commit_refresh(dbs, task)
        logger.info("Updated task %s", task.id)
        return task


async def complete_task(task_id: int) -> Optional[db.Task]:
    return await update_task(task_id, status="completed")


async def delete_task(task_id: int) -> bool:
    async with AsyncSessionLocal() as dbs:
        task = await _get_or_none(dbs, db.Task, task_id)
        if not task:
            return False
        await dbs.delete(task)
        await dbs.commit()
        logger.info("Deleted task %s", task.id)
        return True


# --- Bulk Task Operations ----------------------------------------------------

async def update_all_tasks_status(user_id: str, status: str, *, scope: str = "all") -> int:
    """
    Update status for tasks matching scope for a user.
    scope: 'all' | 'pending' | 'completed'
    Returns number of tasks updated.
    """
    scope = (scope or "all").lower()
    async with AsyncSessionLocal() as dbs:
        result = await dbs.execute(select(db.Task).where(db.Task.user_id == user_id))
        tasks = list(result.scalars())
        count = 0
        for t in tasks:
            if scope == "pending" and t.status == "completed":
                continue
            if scope == "completed" and t.status != "completed":
                continue
            if t.status != status:
                t.status = status
                count += 1
        await dbs.commit()
        logger.info("Bulk updated %d task(s) for user %s with status=%s (scope=%s)", count, user_id, status, scope)
        return count


async def delete_tasks_bulk(user_id: str, *, scope: str = "all") -> int:
    """
    Delete tasks matching scope for a user.
    scope: 'all' | 'pending' | 'completed'
    Returns number of tasks deleted.
    """
    scope = (scope or "all").lower()
    async with AsyncSessionLocal() as dbs:
        result = await dbs.execute(select(db.Task).where(db.Task.user_id == user_id))
        tasks = list(result.scalars())
        count = 0
        for t in tasks:
            if scope == "pending" and t.status == "completed":
                continue
            if scope == "completed" and t.status != "completed":
                continue
            await dbs.delete(t)
            count += 1
        await dbs.commit()
        logger.info("Bulk deleted %d task(s) for user %s (scope=%s)", count, user_id, scope)
        return count


# --- Journal Operations ------------------------------------------------------

async def create_journal(
    user_id: str,
    entry: str,
    summary: Optional[str] = None,
    sentiment: Optional[str] = None,
) -> db.Journal:
    async with AsyncSessionLocal() as dbs:
        journal = db.Journal(user_id=user_id, entry=entry, summary=summary, sentiment=sentiment)
        dbs.add(journal)
        await _commit_refresh(dbs, journal)
        logger.info("Created journal %s for user %s", journal.id, user_id)
        return journal


async def update_journal(
    journal_id: int,
    *,
    entry: Optional[str] = None,
    summary: Optional[str] = None,
    sentiment: Optional[str] = None,
) -> Optional[db.Journal]:
    async with AsyncSessionLocal() as dbs:
        journal = await _get_or_none(dbs, db.Journal, journal_id)
        if not journal:
            return None
        if entry is not None:
            journal.entry = entry
        if summary is not None:
            journal.summary = summary
        if sentiment is not None:
            journal.sentiment = sentiment
        await _commit_refresh(dbs, journal)
        logger.info("Updated journal %s", journal.id)
        return journal


async def delete_journal(journal_id: int) -> bool:
    async with AsyncSessionLocal() as dbs:
        journal = await _get_or_none(dbs, db.Journal, journal_id)
        if not journal:
            return False
        await dbs.delete(journal)
        await dbs.commit()
        logger.info("Deleted journal %s", journal.id)
        return True


async def get_journals(user_id: str, limit: int = 20) -> List[db.Journal]:
    async with AsyncSessionLocal() as dbs:
        result = await dbs.execute(
            select(db.Journal)
            .where(db.Journal.user_id == user_id)
            .order_by(desc(db.Journal.created_at))
            .limit(limit)
        )
        journals = list(result.scalars())
        logger.info("Fetched %d journals for user %s", len(journals), user_id)
        return journals


async def find_journals_by_entry(user_id: str, query: str) -> List[db.Journal]:
    query = (query or "").strip().lower()
    if not query:
        return []
    async with AsyncSessionLocal() as dbs:
        stmt = (
            select(db.Journal)
            .where(db.Journal.user_id == user_id)
            .where(func.lower(db.Journal.entry).like(f"%{query}%"))
            .order_by(desc(db.Journal.created_at))
        )
        result = await dbs.execute(stmt)
        return list(result.scalars())
 
 
async def delete_journals_bulk(user_id: str, *, scope: str = "all") -> int:
    """
    Bulk delete journals for a user.
    Currently supported scopes: 'all'. Returns number of journals deleted.
    """
    scope = (scope or "all").lower()
    async with AsyncSessionLocal() as dbs:
        result = await dbs.execute(select(db.Journal).where(db.Journal.user_id == user_id))
        journals = list(result.scalars())
        count = 0
        if scope == "all":
            for j in journals:
                await dbs.delete(j)
                count += 1
        else:
            # For any unsupported scope, do nothing (future extension point)
            count = 0
        await dbs.commit()
        logger.info("Bulk deleted %d journal(s) for user %s (scope=%s)", count, user_id, scope)
        return count


# --- User Operations ---------------------------------------------------------

async def upsert_user(user_id: str, push_url: Optional[str] = None, push_token: Optional[str] = None) -> db.User:
    """Create or update user with push configuration."""
    async with AsyncSessionLocal() as dbs:
        # Try to find existing user
        result = await dbs.execute(select(db.User).where(db.User.user_id == user_id))
        user = result.scalar_one_or_none()
        
        if user:
            # Update existing user
            if push_url is not None:
                user.push_url = push_url
            if push_token is not None:
                user.push_token = push_token
            user.updated_at = datetime.now(timezone.utc)
            await _commit_refresh(dbs, user)
            logger.info("Updated user %s", user_id)
        else:
            # Create new user
            user = db.User(user_id=user_id, push_url=push_url, push_token=push_token)
            dbs.add(user)
            await _commit_refresh(dbs, user)
            logger.info("Created user %s", user_id)
        
        return user


async def get_user(user_id: str) -> Optional[db.User]:
    """Get user by user_id."""
    async with AsyncSessionLocal() as dbs:
        result = await dbs.execute(select(db.User).where(db.User.user_id == user_id))
        return result.scalar_one_or_none()


# --- Reminder Operations -----------------------------------------------------

async def get_tasks_needing_reminders() -> List[db.Task]:
    """Get all tasks that need reminders sent."""
    now = datetime.now(timezone.utc)
    
    async with AsyncSessionLocal() as dbs:
        # Query for tasks where:
        # 1. Status is pending (not completed/cancelled)
        # 2. Reminders are enabled
        # 3. Has either due_date or reminder_time set
        stmt = (
            select(db.Task)
            .where(db.Task.status == "pending")
            .where(db.Task.reminder_enabled == True)
            .where(
                (db.Task.due_date.isnot(None)) | (db.Task.reminder_time.isnot(None))
            )
        )
        result = await dbs.execute(stmt)
        tasks = list(result.scalars())
        
        logger.info("Found %d tasks potentially needing reminders", len(tasks))
        return tasks


async def mark_reminder_sent(task_id: int) -> bool:
    """Mark that a reminder was sent for this task."""
    async with AsyncSessionLocal() as dbs:
        task = await _get_or_none(dbs, db.Task, task_id)
        if not task:
            return False
        task.last_reminder_sent = datetime.now(timezone.utc)
        await dbs.commit()
        logger.info("Marked reminder sent for task %s", task_id)
        return True
