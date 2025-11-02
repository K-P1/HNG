import logging
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from typing import List
from app import schemas
from app.services import telex_service, task_service, journal_service
from app.utils.json_logger import log_telex_interaction_pretty
import time

logger = logging.getLogger("routes")
router = APIRouter(tags=["Core"])


@router.get("/tasks", response_model=List[schemas.TaskOut])
async def get_tasks(user_id: str):
    return await task_service.list_tasks(user_id)


@router.post("/tasks/complete", response_model=schemas.CompleteTaskResponse)
async def post_complete_task(task_id: int):
    t = await task_service.complete_task(task_id)
    if t is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Task not found")
    return {"status": "ok", "task_id": t.id, "status_after": t.status}


@router.get("/journal", response_model=List[schemas.JournalOut])
async def get_journals(user_id: str, limit: int = 20):
    return await journal_service.list_journals(user_id, limit)


@router.post("/a2a/agent/{agent_name}")
async def reflective_assistant(agent_name: str, request: Request):
    start = time.perf_counter()
    payload = await request.json()
    response = await telex_service.handle_a2a_request(payload)

    try:
        latency_ms = (time.perf_counter() - start) * 1000.0
        client_host = request.client.host if request.client else None
        # Also write a human-friendly pretty log with redactions and summaries
        log_telex_interaction_pretty(
            agent_name=agent_name,
            path=str(request.url.path),
            method="POST",
            request_id=(payload.get("id") if isinstance(payload, dict) else None),
            client_host=client_host,
            request_payload=payload if isinstance(payload, dict) else {"raw": str(payload)},
            response_payload=response if isinstance(response, dict) else {"raw": str(response)},
            status_code=200,
            latency_ms=latency_ms,
        )
    except Exception as e:
        # Do not interrupt the main flow if logging fails
        logger.warning("Failed to log Telex interaction: %s", e)

    return JSONResponse(response)
