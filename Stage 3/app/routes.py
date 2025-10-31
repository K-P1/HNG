
import logging
import os
from dotenv import load_dotenv
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from typing import List
from app import schemas
from app import services

# Load .env so the agent name can be provided there
load_dotenv()

logger = logging.getLogger("routes")

router = APIRouter(tags=["Core"])


@router.get("/health")

def health():
    logger.info("Health check endpoint called.")
    return {"status": "ok"}


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


AGENT_NAME = os.getenv("A2A_AGENT_NAME", os.getenv("AGENT_NAME", "reflectiveAssistant"))


@router.post(f"/a2a/agent/{AGENT_NAME}")
async def reflective_assistant(request: Request):
    """Lean route: accept the raw JSON-RPC payload and delegate handling to services.

    The heavy lifting (parsing, validation, calling LLM/crud, and building the
    JSON-RPC response) lives in `services.handle_a2a_jsonrpc` so routes remain thin.
    """
    payload = await request.json()
    response = services.handle_a2a_jsonrpc(payload)
    return JSONResponse(response)
