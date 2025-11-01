import logging
import asyncio
from fastapi import HTTPException
from app import crud
from app.utils import llm
import uuid
from typing import Any, Dict, List
from app.models.a2a import JSONRPCRequest

logger = logging.getLogger("services")


def _format_tasks_list(tasks: List) -> str:
    """Human-friendly task list used for both immediate replies and follow-ups."""
    if not tasks:
        return "You currently have no pending tasks."

    total = len(tasks)
    pending_count = sum(1 for t in tasks if getattr(t, "status", "pending") != "completed")
    header = f"Here are your tasks (total: {total}, pending: {pending_count}):"
    lines = [header, ""]

    from datetime import datetime

    def friendly(dt):
        if not dt:
            return None
        try:
            if hasattr(dt, "tzinfo") and dt.tzinfo is not None:
                return dt.strftime("%b %d, %Y %I:%M %p %Z")
            return dt.strftime("%b %d, %Y %I:%M %p")
        except Exception:
            try:
                return str(dt)
            except Exception:
                return "N/A"

    for t in tasks:
        desc = getattr(t, "description", None) or str(t)
        status = getattr(t, "status", None) or "pending"
        tid = getattr(t, "id", None)
        created = getattr(t, "created_at", None)
        due = getattr(t, "due_date", None)

        created_str = friendly(created) or "N/A"
        due_str = friendly(due)

        parts = [f"- {desc}", f"status: {status}"]
        if tid is not None:
            parts.append(f"id: {tid}")
        parts.append(f"created: {created_str}")
        if due_str:
            parts.append(f"due: {due_str}")

        lines.append(" (".join([parts[0], ", ".join(parts[1:])]) + ")")

    lines.append("")
    lines.append("Tip: reply 'complete <id>' to mark a task as done.")
    return "\n".join(lines)


async def process_telex_message(user_id: str, message: str) -> dict:
    """Plan and execute actions via LLM only (no heuristics).

    Supports multiple actions in one message.
    """
    logger.info("Processing telex message for user_id=%s", user_id)
    text = (message or "").strip()

    # Ask the LLM to plan actions
    plan = await asyncio.to_thread(llm.plan_actions, text)
    actions = plan.get("actions", []) if isinstance(plan, dict) else []

    # Fallback to legacy single-intent path if no actions are returned
    if not actions:
        intent = await asyncio.to_thread(llm.classify_intent, text)
        logger.info("Fallback intent classified as '%s' for user_id=%s", intent, user_id)
        if intent == "todo":
            try:
                action = await asyncio.to_thread(llm.extract_todo_action, text)
                task = await crud.create_task(user_id, action)
                return {"status": "ok", "message": f'Added "{task.description}" to your todo list.', "task_id": task.id}
            except Exception:
                raise HTTPException(status_code=500, detail="Failed to create task")
        if intent == "journal":
            try:
                sentiment, summary = await asyncio.to_thread(llm.analyze_entry, text)
                journal = await crud.create_journal(user_id, text, summary, sentiment)
                return {"status": "ok", "message": "Journal saved.", "summary": summary, "sentiment": sentiment, "journal_id": journal.id}
            except Exception:
                raise HTTPException(status_code=500, detail="Failed to create journal entry")
        raise HTTPException(status_code=400, detail="Could not determine intent (todo or journal).")

    # Execute actions sequentially and collect a conversational summary
    responses: List[str] = []
    metadata: Dict[str, Any] = {"executed": []}

    from datetime import datetime

    def parse_dt(maybe: Any):
        if not maybe:
            return None
        if isinstance(maybe, datetime):
            return maybe
        if isinstance(maybe, (int, float)):
            try:
                return datetime.fromtimestamp(maybe)
            except Exception:
                return None
        if isinstance(maybe, str):
            for fmt in ("%Y-%m-%d", "%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%SZ"):
                try:
                    return datetime.strptime(maybe, fmt)
                except Exception:
                    continue
        return None

    for a in actions:
        a_type = a.get("type")
        params = a.get("params", {}) if isinstance(a, dict) else {}
        try:
            if a_type == "create_task":
                desc = (params.get("description") or text).strip()
                due = parse_dt(params.get("due_date"))
                task = await crud.create_task(user_id, desc, due_date=due)
                responses.append(f"Added \"{task.description}\" to your todo list (id: {task.id}).")
                metadata["executed"].append({"type": a_type, "task_id": task.id})

            elif a_type == "list_tasks":
                tasks = await crud.get_tasks(user_id)
                responses.append(_format_tasks_list(tasks))
                metadata["executed"].append({"type": a_type, "total": len(tasks)})

            elif a_type == "update_task":
                tid = params.get("id")
                # Allow description-based targeting when id is omitted
                if not tid:
                    desc_q = params.get("description") or params.get("query") or params.get("title")
                    if not desc_q:
                        raise HTTPException(status_code=400, detail="Task id is required for update")
                    matches = await crud.find_tasks_by_description(user_id, str(desc_q))
                    if not matches:
                        raise HTTPException(status_code=404, detail="Task not found")
                    # Prefer most recent
                    tid = matches[0].id
                task = await crud.update_task(
                    int(tid),
                    description=params.get("description"),
                    status=params.get("status"),
                    due_date=parse_dt(params.get("due_date")),
                )
                if not task:
                    raise HTTPException(status_code=404, detail="Task not found")
                note = ""
                if params.get("id") is None and params.get("description"):
                    note = f" (matched by description: '{params.get('description')}')"
                responses.append(f"Updated task #{task.id}.{note}")
                metadata["executed"].append({"type": a_type, "task_id": task.id})

            elif a_type == "delete_task":
                tid = params.get("id")
                if not tid:
                    desc_q = params.get("description") or params.get("query") or params.get("title")
                    if not desc_q:
                        raise HTTPException(status_code=400, detail="Task id is required for delete")
                    matches = await crud.find_tasks_by_description(user_id, str(desc_q))
                    if not matches:
                        raise HTTPException(status_code=404, detail="Task not found")
                    tid = matches[0].id
                ok = await crud.delete_task(int(tid))
                if not ok:
                    raise HTTPException(status_code=404, detail="Task not found")
                note = ""
                if params.get("id") is None and params.get("description"):
                    note = f" (matched by description: '{params.get('description')}')"
                responses.append(f"Deleted task #{int(tid)}.{note}")
                metadata["executed"].append({"type": a_type, "task_id": int(tid)})

            elif a_type == "create_journal":
                entry = (params.get("entry") or text).strip()
                # Optionally analyze to populate summary/sentiment for better UX
                try:
                    sentiment, summary = await asyncio.to_thread(llm.analyze_entry, entry)
                except Exception:
                    sentiment, summary = None, None
                j = await crud.create_journal(user_id, entry, summary, sentiment)
                responses.append(f"Journal saved (id: {j.id}).")
                metadata["executed"].append({"type": a_type, "journal_id": j.id})

            elif a_type == "list_journals":
                limit = params.get("limit") or 20
                js = await crud.get_journals(user_id, int(limit))
                if not js:
                    responses.append("No journal entries yet.")
                else:
                    lines = [f"Your latest {min(len(js), int(limit))} journal entries:", ""]
                    for j in js:
                        lines.append(f"- id {j.id}: {j.summary or (j.entry[:60] + ('…' if len(j.entry) > 60 else ''))}")
                    responses.append("\n".join(lines))
                metadata["executed"].append({"type": a_type, "total": len(js)})

            elif a_type == "update_journal":
                jid = params.get("id")
                if not jid:
                    entry_q = params.get("entry") or params.get("query") or params.get("summary")
                    if not entry_q:
                        raise HTTPException(status_code=400, detail="Journal id is required for update")
                    matches = await crud.find_journals_by_entry(user_id, str(entry_q))
                    if not matches:
                        raise HTTPException(status_code=404, detail="Journal not found")
                    jid = matches[0].id
                j = await crud.update_journal(
                    int(jid),
                    entry=params.get("entry"),
                    summary=params.get("summary"),
                    sentiment=params.get("sentiment"),
                )
                if not j:
                    raise HTTPException(status_code=404, detail="Journal not found")
                note = ""
                if params.get("id") is None and (params.get("entry") or params.get("summary")):
                    note = " (matched by text)"
                responses.append(f"Updated journal #{j.id}.{note}")
                metadata["executed"].append({"type": a_type, "journal_id": j.id})

            elif a_type == "delete_journal":
                jid = params.get("id")
                if not jid:
                    entry_q = params.get("entry") or params.get("query") or params.get("summary")
                    if not entry_q:
                        raise HTTPException(status_code=400, detail="Journal id is required for delete")
                    matches = await crud.find_journals_by_entry(user_id, str(entry_q))
                    if not matches:
                        raise HTTPException(status_code=404, detail="Journal not found")
                    jid = matches[0].id
                ok = await crud.delete_journal(int(jid))
                if not ok:
                    raise HTTPException(status_code=404, detail="Journal not found")
                note = ""
                if params.get("id") is None and (params.get("entry") or params.get("summary")):
                    note = " (matched by text)"
                responses.append(f"Deleted journal #{int(jid)}.{note}")
                metadata["executed"].append({"type": a_type, "journal_id": int(jid)})

            else:
                # Unknown action type — ignore but note
                metadata["executed"].append({"type": a_type, "skipped": True})
        except HTTPException:
            raise
        except Exception as e:
            logger.exception("Action %s failed: %s", a_type, e)
            raise HTTPException(status_code=500, detail=f"Failed to execute action: {a_type}")

    reply = "\n\n".join([r for r in responses if r]) if responses else "Done."
    return {"status": "ok", "message": reply, **metadata}


async def list_tasks(user_id: str):
    logger.info(f"Listing tasks for user_id={user_id}")
    try:
        tasks = await crud.get_tasks(user_id)
        logger.info(f"Fetched {len(tasks)} tasks for user_id={user_id}")
        return tasks
    except Exception as e:
        logger.error(f"Failed to list tasks for user_id={user_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to list tasks")


async def complete_task(task_id: int) -> dict:
    logger.info(f"Completing task id={task_id}")
    try:
        t = await crud.complete_task(task_id)
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


async def list_journals(user_id: str, limit: int = 20):
    logger.info(f"Listing journals for user_id={user_id}, limit={limit}")
    try:
        journals = await crud.get_journals(user_id, limit)
        logger.info(f"Fetched {len(journals)} journals for user_id={user_id}")
        return journals
    except Exception as e:
        logger.error(f"Failed to list journals for user_id={user_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to list journals")


async def handle_a2a_jsonrpc(payload: Dict[str, Any]) -> Dict[str, Any]:
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
        text = str(params)

    try:
        service_result = await process_telex_message(user_id, text)
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


async def handle_jsonrpc_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    try:
        JSONRPCRequest.model_validate(payload)
    except Exception as e:
        logger.warning("Invalid JSON-RPC payload: %s", e)
        request_id = payload.get("id") or ""
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {"code": -32600, "message": "Invalid Request", "data": str(e)},
        }

    try:
        return await handle_a2a_jsonrpc(payload)
    except Exception as e:
        logger.exception("Unhandled exception while handling A2A payload: %s", e)
        request_id = payload.get("id") or ""
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {"code": -32000, "message": "Server error", "data": str(e)},
        }
