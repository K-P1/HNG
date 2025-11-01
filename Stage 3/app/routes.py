
import logging
import os
from dotenv import load_dotenv
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
import asyncio
from app.utils.telex_push import send_telex_followup
from app.utils import llm
from typing import List
from app import schemas
from app import services

load_dotenv()

logger = logging.getLogger("routes")

router = APIRouter(tags=["Core"])


@router.get("/health")

def health():
    logger.info("Health check endpoint called.")
    return {"status": "ok"}


@router.get("/tasks", response_model=List[schemas.TaskOut])

async def get_tasks(user_id: str):
    logger.info(f"/tasks called for user_id={user_id}")
    try:
        tasks = await services.list_tasks(user_id)
        logger.info(f"Fetched {len(tasks)} tasks for user_id={user_id}")
        return tasks
    except Exception as e:
        logger.error(f"Failed to fetch tasks for user_id={user_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch tasks")


@router.post("/tasks/complete", response_model=schemas.CompleteTaskResponse)

async def post_complete_task(task_id: int):
    logger.info(f"/tasks/complete called for task_id={task_id}")
    try:
        result = await services.complete_task(task_id)
        logger.info(f"Task id={task_id} completion processed.")
        return result
    except Exception as e:
        logger.error(f"Failed to complete task id={task_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to complete task")


@router.get("/journal", response_model=List[schemas.JournalOut])

async def get_journals(user_id: str, limit: int = 20):
    logger.info(f"/journal called for user_id={user_id}, limit={limit}")
    try:
        journals = await services.list_journals(user_id, limit)
        logger.info(f"Fetched {len(journals)} journals for user_id={user_id}")
        return journals
    except Exception as e:
        logger.error(f"Failed to fetch journals for user_id={user_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch journals")


AGENT_NAME = os.getenv("A2A_AGENT_NAME", os.getenv("AGENT_NAME", "reflectiveAssistant"))


@router.post(f"/a2a/agent/{AGENT_NAME}")

async def reflective_assistant(request: Request):
    """A lightweight A2A entrypoint that validates the incoming JSON-RPC
    payload against our A2A models.
    If the incoming payload contains a pushNotificationConfig.url we send an
    immediate acknowledgement and spawn a background task that posts the
    final follow-up to the provided push URL.
    """
    try:
        payload = await request.json()
    except Exception:
        # Tolerant fallback to raw bytes -> dict
        try:
            raw = await request.body()
            import json as _json

            payload = _json.loads(raw.decode("utf-8", errors="ignore")) if raw else {}
        except Exception:
            logger.exception("Failed to parse request body as JSON; using empty payload.")
            payload = {}

    # Extract params, message, user and push URL if present
    params = payload.get("params", {}) or {}
    message_obj = params.get("message") or {}
    # Try to pull text from parts like services does
    user_message = ""
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
        user_message = " ".join(texts).strip()
    if not user_message:
        user_message = (message_obj.get("text") if isinstance(message_obj, dict) else None) or params.get("text") or ""

    user_id = params.get("user_id") or (message_obj.get("user_id") if isinstance(message_obj, dict) else None) or params.get("userId") or "unknown-user"

    push_url = None
    push_config = {}
    try:
        push_config = params.get("configuration", {}).get("pushNotificationConfig", {}) or {}
        push_url = push_config.get("url")
    except Exception:
        push_url = None
        push_config = {}
    try:
        # Redacted visibility into push config presence (no secrets leaked)
        schemes = None
        auth = push_config.get("authentication") if isinstance(push_config, dict) else None
        if isinstance(auth, dict):
            s = auth.get("schemes")
            schemes = s if isinstance(s, list) else None
        logger.info(
            "Telex push config received: url=%s, token_present=%s, schemes=%s",
            push_url,
            bool(push_config.get("token")) if isinstance(push_config, dict) else False,
            schemes,
        )
    except Exception:
        pass

    # If we have a push URL, send immediate acknowledgement and spawn follow-up
    if push_url:
        request_id = payload.get("id", "1")
        # Try to plan steps quickly to show a preview in the immediate acknowledgement
        preview_text = "I'll compile your pending to-do list for you. Just a moment while I fetch that information!"
        try:
            plan = await asyncio.to_thread(llm.plan_actions, user_message)
            acts = plan.get("actions", []) if isinstance(plan, dict) else []
            if acts:
                def step_label(a: dict) -> str:
                    t = (a.get("type") or "").strip()
                    p = a.get("params") or {}
                    if t == "create_task":
                        d = (p.get("description") or p.get("title") or "task").strip()
                        due = p.get("due_date") or p.get("due")
                        return f"create task \"{d}\"" + (f" (due: {due})" if isinstance(due, str) and due.strip() else "")
                    if t == "list_tasks":
                        return "list tasks"
                    if t == "update_task":
                        target = p.get("id") or p.get("description") or p.get("query") or p.get("title") or "task"
                        status = p.get("status")
                        if status:
                            return f"update task {target} (status: {status})"
                        return f"update task {target}"
                    if t == "delete_task":
                        target = p.get("id") or p.get("description") or p.get("query") or p.get("title") or "task"
                        return f"delete task {target}"
                    if t == "create_journal":
                        return "create journal entry"
                    if t == "list_journals":
                        return "list journals"
                    if t == "update_journal":
                        return "update journal"
                    if t == "delete_journal":
                        return "delete journal"
                    return t or "step"

                labels = [step_label(a) for a in acts]
                preview_text = f"Planned steps ({len(labels)}): " + "; ".join(labels) + ". I'll post results shortly."
        except Exception:
            # Keep the generic preview if planning preview fails
            pass

        immediate_reply = {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "messages": [
                    {"role": "assistant", "content": preview_text}
                ],
                "metadata": {"status": "processing"}
            }
        }

        async def process_followup():
            # Execute the user's message via the LLM-driven planner and push the summary
            try:
                result = await services.process_telex_message(user_id, user_message)
                if isinstance(result, dict):
                    msg = result.get("message") or "Done."
                else:
                    msg = str(result)
                await send_telex_followup(str(push_url), "[Follow-up]\n\n" + msg, push_config, request_id)
            except Exception as e:
                logger.exception("Error in background follow-up task: %s", e)
                # Push the error back so the user is informed quickly
                try:
                    await send_telex_followup(str(push_url), f"[Follow-up]\n\nError: {e}", push_config, request_id)
                except Exception:
                    pass

        asyncio.create_task(process_followup())
        return JSONResponse(immediate_reply)

    # Fallback to the async JSON-RPC handler if no push URL
    response = await services.handle_jsonrpc_payload(payload)
    return JSONResponse(response)
