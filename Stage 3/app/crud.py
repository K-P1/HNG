from typing import Optional, List
from app.database import SessionLocal
from app import models


def create_task(user_id: str, description: str) -> models.Task:
    db = SessionLocal()
    try:
        task = models.Task(user_id=user_id, description=description)
        db.add(task)
        db.commit()
        db.refresh(task)
        return task
    finally:
        db.close()


def get_tasks(user_id: str) -> List[models.Task]:
    db = SessionLocal()
    try:
        return db.query(models.Task).filter(models.Task.user_id == user_id).all()
    finally:
        db.close()


def complete_task(task_id: int) -> Optional[models.Task]:
    db = SessionLocal()
    try:
        task = db.query(models.Task).get(task_id)
        if not task:
            return None
        task.status = "completed"
        db.commit()
        db.refresh(task)
        return task
    finally:
        db.close()


def create_journal(user_id: str, entry: str, summary: Optional[str] = None, sentiment: Optional[str] = None) -> models.Journal:
    db = SessionLocal()
    try:
        j = models.Journal(user_id=user_id, entry=entry, summary=summary, sentiment=sentiment)
        db.add(j)
        db.commit()
        db.refresh(j)
        return j
    finally:
        db.close()


def get_journals(user_id: str, limit: int = 20) -> List[models.Journal]:
    db = SessionLocal()
    try:
        return (
            db.query(models.Journal)
            .filter(models.Journal.user_id == user_id)
            .order_by(models.Journal.created_at.desc())
            .limit(limit)
            .all()
        )
    finally:
        db.close()
