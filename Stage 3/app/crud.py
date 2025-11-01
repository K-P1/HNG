
import logging
from typing import Optional, List
import logging
from typing import Optional, List
from app.database import AsyncSessionLocal
from app.models.models import Task, Journal
from sqlalchemy import select

logger = logging.getLogger("crud")


async def create_task(user_id: str, description: str) -> Task:
    async with AsyncSessionLocal() as db:
        try:
            task = Task(user_id=user_id, description=description)
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
