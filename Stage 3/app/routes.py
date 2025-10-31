
import logging
from fastapi import APIRouter, HTTPException
from typing import List
from app import schemas
from app import services

logger = logging.getLogger("routes")

router = APIRouter(tags=["Core"])


@router.get("/health")

def health():
    logger.info("Health check endpoint called.")
    return {"status": "ok"}


@router.post("/telex-agent", response_model=schemas.TelexResponse)

def telex_agent(payload: schemas.TelexMessage):
    logger.info(f"/telex-agent called for user_id={payload.user_id}")
    try:
        response = services.process_telex_message(payload.user_id, payload.message)
        logger.info(f"Telex agent processed successfully for user_id={payload.user_id}")
        return response
    except HTTPException as he:
        logger.warning(f"HTTPException in telex_agent for user_id={payload.user_id}: {he.detail}")
        raise
    except Exception as e:
        logger.error(f"LLM error in telex_agent for user_id={payload.user_id}: {e}")
        raise HTTPException(status_code=503, detail=f"LLM error: {e}")


@router.get("/tasks", response_model=List[schemas.TaskOut])

def get_tasks(user_id: str):
    logger.info(f"/tasks called for user_id={user_id}")
    try:
        tasks = services.list_tasks(user_id)
        logger.info(f"Fetched {len(tasks)} tasks for user_id={user_id}")
        return tasks
    except Exception as e:
        logger.error(f"Failed to fetch tasks for user_id={user_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch tasks")


@router.post("/tasks/complete", response_model=schemas.CompleteTaskResponse)

def post_complete_task(task_id: int):
    logger.info(f"/tasks/complete called for task_id={task_id}")
    try:
        result = services.complete_task(task_id)
        logger.info(f"Task id={task_id} completion processed.")
        return result
    except Exception as e:
        logger.error(f"Failed to complete task id={task_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to complete task")


@router.get("/journal", response_model=List[schemas.JournalOut])

def get_journals(user_id: str, limit: int = 20):
    logger.info(f"/journal called for user_id={user_id}, limit={limit}")
    try:
        journals = services.list_journals(user_id, limit)
        logger.info(f"Fetched {len(journals)} journals for user_id={user_id}")
        return journals
    except Exception as e:
        logger.error(f"Failed to fetch journals for user_id={user_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch journals")
