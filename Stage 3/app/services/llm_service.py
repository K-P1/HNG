"""
LLM service: plans and executes user actions
Flow: extract_actions (via LLM) → execute each action (CRUD)
"""
import logging
import asyncio
from typing import Any, Dict, List
from app.utils import llm
from app import crud
from app.services.common import parse_dt

logger = logging.getLogger("llm_service")


def _normalize_desc(s: str) -> str:
    """Normalize description for duplicate detection."""
    return " ".join(str(s).strip().lower().split())


async def plan_actions(text: str) -> Dict[str, Any]:
    """Extract actions from user message using LLM."""
    result = await asyncio.to_thread(llm.extract_actions, text)
    return result


async def execute_actions(user_id: str, actions: List[Dict[str, Any]], original_text: str = "") -> Dict[str, Any]:
    """Execute planned actions against CRUD layer."""
    responses = []
    executed = []
    errors = []
    task_list = None

    for act in actions:
        t = act.get("type")
        a = act.get("action")
        p = act.get("params", {})

        try:
            # TODO actions
            if t == "todo":
                if a == "create":
                    desc = p.get("description", "").strip()
                    if not desc:
                        responses.append("Missing task description.")
                        errors.append({"type": "todo.create", "reason": "missing_description"})
                        continue

                    # Check duplicates
                    existing = await crud.get_tasks(user_id)
                    if any(_normalize_desc(tsk.description) == _normalize_desc(desc) for tsk in existing):
                        responses.append(f"Task already exists: '{desc}'")
                        executed.append({"type": "todo.create.duplicate", "description": desc})
                        continue

                    # Create task
                    due = parse_dt(p.get("due_date") or p.get("due"))
                    task = await crud.create_task(user_id, desc, due_date=due)
                    msg = f"Added '{task.description}' (id: {task.id})"
                    if due:
                        msg += f" due {due.strftime('%b %d, %Y %I:%M %p')}"
                    responses.append(msg)
                    executed.append({"type": "todo.create", "task_id": task.id})

                elif a == "read":
                    # Parse filters
                    status = p.get("status")
                    limit = int(p["limit"]) if p.get("limit") and str(p["limit"]).isdigit() else None
                    due_before = parse_dt(p.get("dueBefore") or p.get("due_before"))
                    due_after = parse_dt(p.get("dueAfter") or p.get("due_after"))
                    query = p.get("query") or p.get("description") or p.get("title")
                    tags = p.get("tags")
                    if isinstance(tags, str):
                        tags = [tags]

                    # Query tasks
                    tasks = await crud.get_tasks_filtered(
                        user_id, status=status, limit=limit,
                        due_before=due_before, due_after=due_after,
                        query=query, tags=tags
                    )

                    if not tasks:
                        responses.append("No tasks found.")
                    else:
                        lines = ["Here are your tasks:"] + [f"- {t.id}: {t.description} [{t.status}]" for t in tasks]
                        responses.append("\n".join(lines))

                    # Store task list for artifacts
                    task_list = [{
                        "id": t.id,
                        "description": t.description,
                        "status": t.status,
                        "due_date": t.due_date.isoformat() if t.due_date else None,
                        "created_at": t.created_at.isoformat() if t.created_at else None,
                    } for t in tasks]
                    executed.append({"type": "todo.read", "count": len(tasks)})

                elif a == "update":
                    scope = p.get("scope", "").strip().lower()
                    
                    # Bulk update
                    if scope in {"all", "pending", "completed"}:
                        status_to = p.get("status")
                        if not status_to:
                            responses.append("Missing target status for bulk update.")
                            errors.append({"type": "todo.update.bulk", "reason": "missing_status"})
                            continue
                        
                        count = await crud.update_all_tasks_status(user_id, status_to, scope=scope)
                        responses.append(f"Updated {count} task(s).")
                        executed.append({"type": "todo.update.bulk", "count": count})
                    
                    # Single update
                    else:
                        tid = p.get("id")
                        if not tid:
                            desc_q = p.get("description") or p.get("query")
                            if not desc_q:
                                responses.append("Missing task id or description.")
                                errors.append({"type": "todo.update", "reason": "missing_identifier"})
                                continue
                            
                            matches = await crud.find_tasks_by_description(user_id, desc_q)
                            if not matches:
                                responses.append(f"Task not found: '{desc_q}'")
                                errors.append({"type": "todo.update", "reason": "not_found"})
                                continue
                            tid = matches[0].id
                        
                        try:
                            tid = int(tid)
                        except (TypeError, ValueError):
                            responses.append(f"Couldn't update task: invalid id '{tid}'.")
                            errors.append({"type": "todo.update", "reason": "invalid_id"})
                            continue
                        
                        task = await crud.update_task(
                            tid,
                            description=p.get("description"),
                            status=p.get("status"),
                            due_date=parse_dt(p.get("due_date"))
                        )
                        
                        if not task:
                            responses.append(f"Task #{tid} not found.")
                            errors.append({"type": "todo.update", "reason": "not_found"})
                            continue
                        
                        responses.append(f"Updated task #{task.id}.")
                        executed.append({"type": "todo.update", "task_id": task.id})

                elif a == "delete":
                    scope = (p.get("scope") or "").strip().lower()
                    if scope in {"all", "pending", "completed"}:
                        count = await crud.delete_tasks_bulk(user_id, scope=scope)
                        responses.append(f"Deleted {count} task(s).")
                        executed.append({"type": "todo.delete.bulk", "count": count, "scope": scope})
                    else:
                        tid = p.get("id")
                        if not tid:
                            desc_q = p.get("description") or p.get("query") or p.get("title")
                            if not desc_q:
                                msg = "Couldn't delete task: no id or description provided."
                                responses.append(msg)
                                errors.append({"type": "todo.delete", "reason": "missing_identifier"})
                                continue
                            matches = await crud.find_tasks_by_description(user_id, str(desc_q))
                            if not matches:
                                msg = f"Couldn't find a task matching '{str(desc_q)}' to delete."
                                responses.append(msg)
                                errors.append({"type": "todo.delete", "reason": "not_found", "query": str(desc_q)})
                                continue
                            tid = matches[0].id
                        ok = await crud.delete_task(int(tid))
                        if not ok:
                            msg = f"Task #{int(tid)} wasn't found to delete."
                            responses.append(msg)
                            errors.append({"type": "todo.delete", "reason": "not_found", "task_id": int(tid)})
                            continue
                        responses.append(f"Deleted task #{int(tid)}.")
                        executed.append({"type": "todo.delete", "task_id": int(tid)})

            elif t == "journal":
                if a == "create":
                    provided_entry = p.get("entry")
                    if not isinstance(provided_entry, str) or not provided_entry.strip():
                        logger.warning("journal.create: missing required entry parameter for user %s", user_id)
                        msg = "Could not create journal entry: missing content. Please provide what you'd like to journal."
                        responses.append(msg)
                        errors.append({"type": "journal.create", "reason": "missing_entry", "params": p})
                        continue
                    entry = provided_entry.strip()
                    logger.info("journal.create: using planner entry (len=%d)", len(entry))
                    j = await crud.create_journal(user_id, entry, None, None)
                    responses.append(f"Journal saved (id: {j.id}).")
                    executed.append({"type": "journal.create", "journal_id": j.id})

                elif a == "read":
                    limit = p.get("limit") or 20
                    js = await crud.get_journals(user_id, int(limit))
                    if not js:
                        responses.append("No journal entries yet.")
                    else:
                        lines = [f"Your latest {min(len(js), int(limit))} journal entries:"]
                        for j in js:
                            lines.append(f"- id {j.id}: {j.summary or j.entry[:60]}")
                        responses.append("\n".join(lines))
                    executed.append({"type": "journal.read", "total": len(js)})

                elif a == "update":
                    jid = p.get("id")
                    if not jid:
                        entry_q = p.get("entry") or p.get("summary")
                        if not entry_q:
                            msg = "Couldn't update journal: no id or entry text provided."
                            responses.append(msg)
                            errors.append({"type": "journal.update", "reason": "missing_identifier"})
                            continue
                        matches = await crud.find_journals_by_entry(user_id, str(entry_q))
                        if not matches:
                            msg = f"Couldn't find a journal matching the provided text to update."
                            responses.append(msg)
                            errors.append({"type": "journal.update", "reason": "not_found", "query": str(entry_q)})
                            continue
                        jid = matches[0].id
                    j = await crud.update_journal(
                        int(jid),
                        entry=p.get("entry"),
                        summary=p.get("summary"),
                        sentiment=p.get("sentiment"),
                    )
                    if j is None:
                        msg = f"Journal #{int(jid)} wasn't found to update."
                        responses.append(msg)
                        errors.append({"type": "journal.update", "reason": "not_found", "journal_id": int(jid)})
                        continue
                    responses.append(f"Updated journal #{j.id}.")
                    executed.append({"type": "journal.update", "journal_id": j.id})

                elif a == "delete":
                    scope = (p.get("scope") or "").strip().lower()
                    if scope in {"all"}:
                        count = await crud.delete_journals_bulk(user_id, scope=scope)
                        responses.append(f"Deleted {count} journal(s).")
                        executed.append({"type": "journal.delete.bulk", "count": count, "scope": scope})
                    else:
                        jid = p.get("id")
                        if not jid:
                            entry_q = p.get("entry") or p.get("summary")
                            if not entry_q:
                                msg = "Couldn't delete journal: no id or entry text provided."
                                responses.append(msg)
                                errors.append({"type": "journal.delete", "reason": "missing_identifier"})
                                continue
                            matches = await crud.find_journals_by_entry(user_id, str(entry_q))
                            if not matches:
                                msg = f"Couldn't find a journal matching the provided text to delete."
                                responses.append(msg)
                                errors.append({"type": "journal.delete", "reason": "not_found", "query": str(entry_q)})
                                continue
                            jid = matches[0].id
                        ok = await crud.delete_journal(int(jid))
                        if not ok:
                            msg = f"Journal #{int(jid)} wasn't found to delete."
                            responses.append(msg)
                            errors.append({"type": "journal.delete", "reason": "not_found", "journal_id": int(jid)})
                            continue
                        responses.append(f"Deleted journal #{int(jid)}.")
                        executed.append({"type": "journal.delete", "journal_id": int(jid)})

            elif t == "unknown":
                # Handle unclassifiable intents gracefully - no database operations
                logger.info("execute_actions: encountered 'unknown' type for user %s, action=%s", user_id, a)
                msg = "I couldn't determine if this should be a task or journal entry. Please be more specific about what you'd like to do."
                responses.append(msg)
                # Record as soft error for visibility
                errors.append({
                    "type": "unknown",
                    "action": a,
                    "reason": "unclassifiable_intent"
                })
                continue

            else:
                # Gracefully handle truly unknown types (shouldn't happen after 'unknown' handling)
                logger.warning("execute_actions: unknown action type '%s' for user %s", t, user_id)
                msg = f"I couldn't understand the type of action requested (type: {t}). This text might not be meant for task or journal management."
                responses.append(msg)
                errors.append({"type": t, "action": a, "reason": "unsupported_type", "params": p})
                continue

        except Exception as e:
            # Never raise - convert all exceptions to soft errors
            logger.exception("Action execution failed for user %s, type=%s, action=%s: %s", user_id, t, a, e)
            msg = f"An error occurred while processing your request: {str(e)}"
            responses.append(msg)
            errors.append({
                "type": t or "unknown",
                "action": a or "unknown",
                "reason": "execution_exception",
                "error": str(e)
            })
            continue

    # Build result
    message = "\n\n".join(responses) if len(responses) > 1 else (responses[0] if responses else "Done.")
    
    result = {
        "status": "ok",
        "message": message,
        "executed": executed,
    }
    
    if errors:
        result["errors"] = errors
    if task_list is not None:
        result["task_list"] = task_list
    
    return result


async def analyze_entry(entry: str):
    """Lightweight stub for journal analysis (sentiment, summary)."""
    return None, None

