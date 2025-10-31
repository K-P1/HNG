
import logging
from typing import Optional, List
import logging
from typing import Optional, List
from app.database import SessionLocal
from app.models.models import Task, Journal

logger = logging.getLogger("crud")


def create_task(user_id: str, description: str) -> Task:
    db = SessionLocal()
    try:
        task = Task(user_id=user_id, description=description)
        db.add(task)
        db.commit()
        db.refresh(task)
        logger.info(f"Task created successfully for user_id={user_id}, task_id={task.id}")
        return task
    except Exception as e:
        logger.error(f"Failed to create task for user_id={user_id}: {e}")
        raise
    finally:
        db.close()


def get_tasks(user_id: str) -> List[Task]:
    db = SessionLocal()
    try:
        tasks = db.query(Task).filter(Task.user_id == user_id).all()
        logger.info(f"Fetched {len(tasks)} tasks for user_id={user_id}")
        return tasks
    except Exception as e:
        logger.error(f"Failed to fetch tasks for user_id={user_id}: {e}")
        raise
    finally:
        db.close()


def complete_task(task_id: int) -> Optional[Task]:
    db = SessionLocal()
    try:
        task = db.query(Task).get(task_id)
        if not task:
            logger.warning(f"Task with id={task_id} not found for completion.")
            return None
        task.status = "completed"
        db.commit()
        db.refresh(task)
        logger.info(f"Task id={task_id} marked as completed.")
        return task
    except Exception as e:
        logger.error(f"Failed to complete task id={task_id}: {e}")
        raise
    finally:
        db.close()


def create_journal(user_id: str, entry: str, summary: Optional[str] = None, sentiment: Optional[str] = None) -> Journal:
    db = SessionLocal()
    try:
        j = Journal(user_id=user_id, entry=entry, summary=summary, sentiment=sentiment)
        db.add(j)
        db.commit()
        db.refresh(j)
        logger.info(f"Journal entry created for user_id={user_id}, journal_id={j.id}")
        return j
    except Exception as e:
        logger.error(f"Failed to create journal entry for user_id={user_id}: {e}")
        raise
    finally:
        db.close()


def get_journals(user_id: str, limit: int = 20) -> List[Journal]:
    db = SessionLocal()
    try:
        journals = (
            db.query(Journal)
            .filter(Journal.user_id == user_id)
            .order_by(Journal.created_at.desc())
            .limit(limit)
            .all()
        )
        logger.info(f"Fetched {len(journals)} journals for user_id={user_id}")
        return journals
    except Exception as e:
        logger.error(f"Failed to fetch journals for user_id={user_id}: {e}")
        raise
    finally:
        db.close()
        raise
