from fastapi import APIRouter, HTTPException
from typing import List
from app import schemas
from app import services

router = APIRouter(tags=["Core"])


@router.get("/health")
def health():
    return {"status": "ok"}


@router.post("/telex-agent", response_model=schemas.TelexResponse)
def telex_agent(payload: schemas.TelexMessage):
    try:
        return services.process_telex_message(payload.user_id, payload.message)
    except HTTPException:
        raise
    except Exception as e:
        # Fail fast if LLM is misconfigured/unavailable
        raise HTTPException(status_code=503, detail=f"LLM error: {e}")


@router.get("/tasks", response_model=List[schemas.TaskOut])
def get_tasks(user_id: str):
    return services.list_tasks(user_id)


@router.post("/tasks/complete", response_model=schemas.CompleteTaskResponse)
def post_complete_task(task_id: int):
    return services.complete_task(task_id)


@router.get("/journal", response_model=List[schemas.JournalOut])
def get_journals(user_id: str, limit: int = 20):
    return services.list_journals(user_id, limit)
