import logging
from typing import Optional, List
from datetime import datetime
from app import crud

logger = logging.getLogger("services.task")


async def create_task(
    user_id: str, 
    description: str, 
    due_date: Optional[datetime] = None,
    reminder_time: Optional[datetime] = None,
    reminder_enabled: bool = True
):
    return await crud.create_task(
        user_id, 
        description, 
        due_date=due_date,
        reminder_time=reminder_time,
        reminder_enabled=reminder_enabled
    )


async def list_tasks(user_id: str) -> List:
    return await crud.get_tasks(user_id)


async def find_tasks_by_description(user_id: str, query: str) -> List:
    return await crud.find_tasks_by_description(user_id, query)


async def update_task(task_id: int, **kwargs):
    return await crud.update_task(task_id, **kwargs)


async def complete_task(task_id: int):
    return await crud.complete_task(task_id)


async def delete_task(task_id: int):
    return await crud.delete_task(task_id)
