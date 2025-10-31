
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
    # Read the raw body first so we can avoid raising JSONDecodeError when
    # the incoming request has an empty body or non-JSON content.
    body = await request.body()
    # If DEBUG=true, log the raw body contents (helpful while integrating Telex).
    # We use a tolerant decode so logging never raises.
    try:
        debug_enabled = os.getenv("DEBUG", "false").lower() in ("1", "true", "yes")
    except Exception:
        debug_enabled = False

    if debug_enabled:
        try:
            raw_text = body.decode("utf-8", errors="replace") if body else ""
            logger.debug(f"A2A raw body: {raw_text}")
        except Exception:
            logger.debug("A2A raw body: <unprintable binary>")
    if not body or body.strip() == b"":
        logger.warning("Empty body received on A2A endpoint; delegating empty payload to service.")
        payload = {}
    else:
        try:
            # Preferred path: FastAPI's json() which respects request charset
            payload = await request.json()
        except Exception:
            # Fallback: try a tolerant decode from raw bytes
            try:
                import json as _json

                payload = _json.loads(body.decode("utf-8", errors="ignore"))
            except Exception:
                logger.exception("Failed to parse request body as JSON; delegating empty payload to service.")
                payload = {}

    response = services.handle_a2a_jsonrpc(payload)
    return JSONResponse(response)
