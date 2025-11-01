
import logging
from typing import Optional, List
from datetime import datetime
import logging
from typing import Optional, List
from app.database import AsyncSessionLocal
from app.models.models import Task, Journal
from sqlalchemy import select, func, desc

logger = logging.getLogger("crud")


async def create_task(user_id: str, description: str, due_date: Optional[datetime] = None) -> Task:
    async with AsyncSessionLocal() as db:
        try:
            task = Task(user_id=user_id, description=description)
            if due_date is not None:
                task.due_date = due_date
            db.add(task)
            await db.commit()
            await db.refresh(task)
            logger.info(f"Task created successfully for user_id={user_id}, task_id={task.id}")
            return task
        except Exception as e:
            logger.error(f"Failed to create task for user_id={user_id}: {e}")
            raise


async def get_tasks(user_id: str) -> List[Task]:
    async with AsyncSessionLocal() as db:
        try:
            result = await db.execute(select(Task).where(Task.user_id == user_id))
            tasks = list(result.scalars())
            logger.info(f"Fetched {len(tasks)} tasks for user_id={user_id}")
            return tasks
        except Exception as e:
            logger.error(f"Failed to fetch tasks for user_id={user_id}: {e}")
            raise


async def find_tasks_by_description(user_id: str, query: str) -> List[Task]:
    """Find tasks where description contains the query (case-insensitive), most recent first."""
    async with AsyncSessionLocal() as db:
        try:
            q = (query or "").strip().lower()
            if not q:
                return []
            stmt = (
                select(Task)
                .where(Task.user_id == user_id)
                .where(func.lower(Task.description).like(f"%{q}%"))
                .order_by(desc(Task.created_at))
            )
            result = await db.execute(stmt)
            return list(result.scalars())
        except Exception as e:
            logger.error("Failed to search tasks for user_id=%s: %s", user_id, e)
            raise


async def complete_task(task_id: int) -> Optional[Task]:
    async with AsyncSessionLocal() as db:
        try:
            task = await db.get(Task, task_id)
            if not task:
                logger.warning(f"Task with id={task_id} not found for completion.")
                return None
            task.status = "completed"
            await db.commit()
            await db.refresh(task)
            logger.info(f"Task id={task_id} marked as completed.")
            return task
        except Exception as e:
            logger.error(f"Failed to complete task id={task_id}: {e}")
            raise


async def update_task(task_id: int, *, description: Optional[str] = None, status: Optional[str] = None, due_date: Optional[datetime] = None) -> Optional[Task]:
    async with AsyncSessionLocal() as db:
        try:
            task = await db.get(Task, task_id)
            if not task:
                logger.warning("Task with id=%s not found for update.", task_id)
                return None
            if description is not None:
                task.description = description
            if status is not None:
                task.status = status
            if due_date is not None:
                task.due_date = due_date
            await db.commit()
            await db.refresh(task)
            logger.info("Task id=%s updated.", task_id)
            return task
        except Exception as e:
            logger.error("Failed to update task id=%s: %s", task_id, e)
            raise


async def delete_task(task_id: int) -> bool:
    async with AsyncSessionLocal() as db:
        try:
            task = await db.get(Task, task_id)
            if not task:
                logger.warning("Task with id=%s not found for delete.", task_id)
                return False
            await db.delete(task)
            await db.commit()
            logger.info("Task id=%s deleted.", task_id)
            return True
        except Exception as e:
            logger.error("Failed to delete task id=%s: %s", task_id, e)
            raise


async def create_journal(user_id: str, entry: str, summary: Optional[str] = None, sentiment: Optional[str] = None) -> Journal:
    async with AsyncSessionLocal() as db:
        try:
            j = Journal(user_id=user_id, entry=entry, summary=summary, sentiment=sentiment)
            db.add(j)
            await db.commit()
            await db.refresh(j)
            logger.info(f"Journal entry created for user_id={user_id}, journal_id={j.id}")
            return j
        except Exception as e:
            logger.error(f"Failed to create journal entry for user_id={user_id}: {e}")
            raise


async def update_journal(journal_id: int, *, entry: Optional[str] = None, summary: Optional[str] = None, sentiment: Optional[str] = None) -> Optional[Journal]:
    async with AsyncSessionLocal() as db:
        try:
            j = await db.get(Journal, journal_id)
            if not j:
                logger.warning("Journal with id=%s not found for update.", journal_id)
                return None
            if entry is not None:
                j.entry = entry
            if summary is not None:
                j.summary = summary
            if sentiment is not None:
                j.sentiment = sentiment
            await db.commit()
            await db.refresh(j)
            logger.info("Journal id=%s updated.", journal_id)
            return j
        except Exception as e:
            logger.error("Failed to update journal id=%s: %s", journal_id, e)
            raise


async def delete_journal(journal_id: int) -> bool:
    async with AsyncSessionLocal() as db:
        try:
            j = await db.get(Journal, journal_id)
            if not j:
                logger.warning("Journal with id=%s not found for delete.", journal_id)
                return False
            await db.delete(j)
            await db.commit()
            logger.info("Journal id=%s deleted.", journal_id)
            return True
        except Exception as e:
            logger.error("Failed to delete journal id=%s: %s", journal_id, e)
            raise


async def get_journals(user_id: str, limit: int = 20) -> List[Journal]:
    async with AsyncSessionLocal() as db:
        try:
            result = await db.execute(
                select(Journal)
                .where(Journal.user_id == user_id)
                .order_by(Journal.created_at.desc())
                .limit(limit)
            )
            journals = list(result.scalars())
            logger.info(f"Fetched {len(journals)} journals for user_id={user_id}")
            return journals
        except Exception as e:
            logger.error(f"Failed to fetch journals for user_id={user_id}: {e}")
            raise


async def find_journals_by_entry(user_id: str, query: str) -> List[Journal]:
    """Find journals where entry contains the query (case-insensitive), most recent first."""
    async with AsyncSessionLocal() as db:
        try:
            q = (query or "").strip().lower()
            if not q:
                return []
            stmt = (
                select(Journal)
                .where(Journal.user_id == user_id)
                .where(func.lower(Journal.entry).like(f"%{q}%"))
                .order_by(desc(Journal.created_at))
            )
            result = await db.execute(stmt)
            return list(result.scalars())
        except Exception as e:
            logger.error("Failed to search journals for user_id=%s: %s", user_id, e)
            raise
