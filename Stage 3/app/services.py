import logging
from fastapi import HTTPException
from app import crud
from app.utils import llm
import uuid
from fastapi import HTTPException
from typing import Any, Dict

logger = logging.getLogger("services")



def process_telex_message(user_id: str, message: str) -> dict:
    """Classify message and perform the corresponding action using Groq."""
    logger.info(f"Processing telex message for user_id={user_id}")
    intent = llm.classify_intent(message)
    logger.info(f"Intent classified as '{intent}' for user_id={user_id}")
    if intent == "todo":
        try:
            action = llm.extract_todo_action(message)
            task = crud.create_task(user_id, action)
            logger.info(f"Task created for user_id={user_id}, task_id={task.id}")
            return {"status": "ok", "message": f'Added "{task.description}" to your todo list.', "task_id": task.id}
        except Exception as e:
            logger.error(f"Failed to create task for user_id={user_id}: {e}")
            raise HTTPException(status_code=500, detail="Failed to create task")

    if intent == "journal":
        try:
            sentiment, summary = llm.analyze_entry(message)
            journal = crud.create_journal(user_id, message, summary, sentiment)
            logger.info(f"Journal entry created for user_id={user_id}, journal_id={journal.id}")
            return {
                "status": "ok",
                "message": "Journal saved.",
                "summary": summary,
                "sentiment": sentiment,
                "journal_id": journal.id,
            }
        except Exception as e:
            logger.error(f"Failed to create journal entry for user_id={user_id}: {e}")
            raise HTTPException(status_code=500, detail="Failed to create journal entry")

    logger.warning(f"Could not determine intent for user_id={user_id}")
    raise HTTPException(status_code=400, detail="Could not determine intent (todo or journal).")



def list_tasks(user_id: str):
    logger.info(f"Listing tasks for user_id={user_id}")
    try:
        tasks = crud.get_tasks(user_id)
        logger.info(f"Fetched {len(tasks)} tasks for user_id={user_id}")
        return tasks
    except Exception as e:
        logger.error(f"Failed to list tasks for user_id={user_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to list tasks")



def complete_task(task_id: int) -> dict:
    logger.info(f"Completing task id={task_id}")
    try:
        t = crud.complete_task(task_id)
        if not t:
            logger.warning(f"Task id={task_id} not found for completion.")
            raise HTTPException(status_code=404, detail="Task not found")
        logger.info(f"Task id={task_id} marked as completed.")
        return {"status": "ok", "task_id": t.id, "status_after": t.status}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to complete task id={task_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to complete task")



def list_journals(user_id: str, limit: int = 20):
    logger.info(f"Listing journals for user_id={user_id}, limit={limit}")
    try:
        journals = crud.get_journals(user_id, limit)
        logger.info(f"Fetched {len(journals)} journals for user_id={user_id}")
        return journals
    except Exception as e:
        logger.error(f"Failed to list journals for user_id={user_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to list journals")


def handle_a2a_jsonrpc(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Process a Telex A2A JSON-RPC 2.0 payload and return a JSON-RPC response.

    - Ensures the response includes an "id" (echoed or generated).
    - Extracts text from common Telex shapes (message.parts, message.text, params.text).
    - Calls existing `process_telex_message` for domain logic and packages the
      reply under `result.messages` with any extra fields under `result.metadata`.
    """
    request_id = payload.get("id")
    if not request_id:
        # Generate a UUID if no id was provided to respect JSON-RPC contract
        request_id = uuid.uuid4().hex

    params = payload.get("params") or {}
    message_obj = params.get("message") or {}

    # Extract text from message.parts if present
    text = ""
    parts = message_obj.get("parts") if isinstance(message_obj, dict) else None
    if parts and isinstance(parts, list):
        texts = []
        for p in parts:
            if isinstance(p, dict) and p.get("kind") == "text" and p.get("text"):
                texts.append(p.get("text"))
            elif isinstance(p, dict) and p.get("text"):
                texts.append(p.get("text"))
            elif isinstance(p, str):
                texts.append(p)
        text = " ".join(texts).strip()

    # Fallbacks
    if not text:
        text = (message_obj.get("text") if isinstance(message_obj, dict) else None) or params.get("text") or ""

    user_id = params.get("user_id") or (message_obj.get("user_id") if isinstance(message_obj, dict) else None) or params.get("userId") or "unknown-user"

    if not text:
        # If we couldn't find a text payload, include the full params as text to the LLM
        text = str(params)

    try:
        service_result = process_telex_message(user_id, text)
        reply_text = service_result.get("message", "") if isinstance(service_result, dict) else str(service_result)
        metadata = {k: v for k, v in service_result.items() if k != "message"} if isinstance(service_result, dict) else {}
        result = {
            "messages": [
                {"role": "assistant", "content": reply_text}
            ],
            "metadata": metadata,
        }
    except HTTPException as he:
        detail = he.detail if isinstance(he.detail, (str, int, float)) else str(he.detail)
        result = {
            "messages": [{"role": "assistant", "content": detail}],
            "metadata": {"error_status": he.status_code, "error_detail": detail},
        }
    except Exception as e:
        err = str(e)
        result = {
            "messages": [{"role": "assistant", "content": "Internal server error"}],
            "metadata": {"error": err},
        }

    return {"jsonrpc": "2.0", "id": request_id, "result": result}
