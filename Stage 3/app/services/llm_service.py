import logging
import asyncio
from typing import Any, Dict, List
from app.utils import llm
from app import crud
from app.services.common import parse_dt

logger = logging.getLogger("llm_service")


async def plan_actions_strict(user_message: str) -> List[Dict[str, Any]]:
    """
    Wrapper around llm.extract_actions that gracefully handles all failure cases.
    Returns empty list or actions with 'unknown' type when planning fails.
    """
    try:
        result = await asyncio.to_thread(llm.extract_actions, user_message)
        try:
            logger.info("plan_actions_strict: raw planner result for text='%s': %s", user_message, result)
        except Exception:
            logger.warning("plan_actions_strict: unable to log planner result (non-serializable)")
        actions = result.get("actions", []) if isinstance(result, dict) else []
        if not actions:
            logger.warning("Planner returned no actions for message: %s", user_message)
            # Return an 'unknown' type action so downstream can handle it gracefully
            return [{"type": "unknown", "action": "unrecognized", "params": {"original_text": user_message}}]
        return actions
    except Exception as e:
        logger.exception("plan_actions_strict failed: %s", e)
        # Soft fail: return unknown type instead of raising exception
        return [{"type": "unknown", "action": "error", "params": {"original_text": user_message, "error": str(e)}}]


async def plan_actions(text: str) -> Dict[str, Any]:
    """Compatibility wrapper returning {'actions': [...]}"""
    actions = await plan_actions_strict(text)
    return {"actions": actions}


async def execute_actions(user_id: str, actions: List[Dict[str, Any]], original_text: str) -> Dict[str, Any]:
    """
    Executes structured LLM actions against CRUD layer.
    Each action has shape: {"type": "todo"|"journal", "action": "create"|"read"|"update"|"delete", "params": {...}}
    """
    responses: List[str] = []
    metadata: Dict[str, Any] = {"executed": []}
    # Collect soft errors so we can continue executing remaining actions and still inform the user
    metadata_errors: List[Dict[str, Any]] = []

    from datetime import datetime

    for act in actions:
        logger.info("execute_actions: executing action=%s", act)
        t = act.get("type")
        a = act.get("action")
        p = act.get("params", {}) or {}

        try:
            if t == "todo":
                if a == "create":
                    provided_desc = p.get("description")
                    if not isinstance(provided_desc, str) or not provided_desc.strip():
                        logger.warning("todo.create: missing required description parameter for user %s", user_id)
                        msg = "Could not create task: missing description. Please provide what you'd like to add."
                        responses.append(msg)
                        metadata_errors.append({"type": "todo.create", "reason": "missing_description", "params": p})
                        continue
                    desc = provided_desc.strip()
                    logger.info("todo.create: using planner description='%s'", desc)

                    # Duplicate detection (normalized, user-scoped)
                    def _norm(s: str) -> str:
                        return " ".join(str(s).strip().lower().split())
                    
                    existing = await crud.get_tasks(user_id)
                    if any(_norm(tsk.description) == _norm(desc) for tsk in existing):
                        logger.info("todo.create: skipped duplicate '%s' for user %s", desc, user_id)
                        msg = f"Skipped duplicate task: '{desc}'."
                        responses.append(msg)
                        metadata["executed"].append({"type": "todo.create.skipped_duplicate", "description": desc})
                        continue # Skip creation

                    due_raw = p.get("due_date") or p.get("due")
                    due = parse_dt(due_raw)
                    task = await crud.create_task(user_id, desc, due_date=due)
                    due_str = due.strftime("%b %d, %Y %I:%M %p") if due else None
                    msg = f"Added '{task.description}' (id: {task.id})"
                    if due_str:
                        msg += f" due {due_str}"
                    responses.append(msg)
                    metadata["executed"].append({"type": "todo.create", "task_id": task.id})

                elif a == "read":
                    # Extract optional filters from planner params
                    status = (p.get("status") or None)
                    limit = p.get("limit")
                    due_before_raw = p.get("dueBefore") or p.get("due_before")
                    due_after_raw = p.get("dueAfter") or p.get("due_after")
                    query = p.get("query") or p.get("description") or p.get("title")
                    tags = p.get("tags")
                    if isinstance(tags, str):
                        tags = [tags]
                    due_before = parse_dt(due_before_raw)
                    due_after = parse_dt(due_after_raw)

                    tasks = await crud.get_tasks_filtered(
                        user_id,
                        status=status,
                        limit=(int(limit) if isinstance(limit, int) or (isinstance(limit, str) and str(limit).isdigit()) else None),
                        due_before=due_before,
                        due_after=due_after,
                        query=(str(query) if query else None),
                        tags=tags,
                    )

                    # Log concise summary
                    titles_preview = ", ".join([t.description for t in tasks[:3]]) if tasks else ""
                    logger.info(
                        "todo.read: filters status=%s,limit=%s,dueBefore=%s,dueAfter=%s,query=%s,tags=%s -> %d tasks (first3=%s)",
                        status,
                        limit,
                        due_before,
                        due_after,
                        query,
                        tags,
                        len(tasks),
                        titles_preview,
                    )

                    if not tasks:
                        responses.append("No matching tasks found.")
                    else:
                        lines = ["Here are your tasks:"]
                        for tsk in tasks:
                            lines.append(f"- {tsk.id}: {tsk.description} [{tsk.status}]")
                        responses.append("\n".join(lines))

                    # Include structured task list in metadata for artifacts/follow-ups
                    metadata["task_list"] = [
                        {
                            "id": t.id,
                            "description": t.description,
                            "status": t.status,
                            "due_date": (t.due_date.isoformat() if t.due_date else None),
                            "created_at": (t.created_at.isoformat() if t.created_at else None),
                        }
                        for t in tasks
                    ]
                    metadata["executed"].append({
                        "type": "todo.read",
                        "count": len(tasks),
                        "filters": {
                            "status": status,
                            "limit": limit,
                            "dueBefore": (due_before.isoformat() if due_before else None),
                            "dueAfter": (due_after.isoformat() if due_after else None),
                            "query": (str(query) if query else None),
                            "tags": (tags or []),
                        },
                    })

                elif a == "update":
                    scope = (p.get("scope") or "").strip().lower()
                    status_to = p.get("status")
                    if scope in {"all", "all_pending", "pending", "completed"}:
                        # Bulk update (e.g., mark all pending as completed)
                        if not status_to:
                            logger.warning("todo.update.bulk: missing required 'status' parameter for user %s", user_id)
                            msg = "Could not update tasks: missing target status. Please specify what status to set (e.g., 'completed', 'pending')."
                            responses.append(msg)
                            metadata_errors.append({"type": "todo.update.bulk", "reason": "missing_status", "scope": scope})
                            continue
                        normalized_scope = "pending" if scope in {"all_pending", "pending"} else ("completed" if scope == "completed" else "all")
                        count = await crud.update_all_tasks_status(user_id, str(status_to), scope=normalized_scope)
                        responses.append(f"Updated {count} task(s).")
                        metadata["executed"].append({"type": "todo.update.bulk", "count": count, "scope": normalized_scope})
                    else:
                        tid = p.get("id")
                        if not tid:
                            desc_q = p.get("description") or p.get("query") or p.get("title")
                            if not desc_q:
                                # Missing identifier; record and continue
                                msg = "Couldn't update task: no id or description provided."
                                responses.append(msg)
                                metadata_errors.append({"type": "todo.update", "reason": "missing_identifier"})
                                continue
                            matches = await crud.find_tasks_by_description(user_id, str(desc_q))
                            if not matches:
                                msg = f"Couldn't find a task matching '{str(desc_q)}' to update."
                                responses.append(msg)
                                metadata_errors.append({"type": "todo.update", "reason": "not_found", "query": str(desc_q)})
                                continue
                            tid = matches[0].id
                        # Coerce task id to int to satisfy DB driver requirements (e.g., asyncpg)
                        try:
                            tid_int = int(tid)
                        except (TypeError, ValueError):
                            msg = f"Couldn't update task: invalid id '{tid}'."
                            responses.append(msg)
                            metadata_errors.append({"type": "todo.update", "reason": "invalid_id", "task_id": tid})
                            continue
                        task = await crud.update_task(
                            tid_int,
                            description=p.get("description"),
                            status=p.get("status"),
                            due_date=parse_dt(p.get("due_date")),
                        )
                        if task is None:
                            msg = f"Task #{tid_int} wasn't found to update."
                            responses.append(msg)
                            metadata_errors.append({"type": "todo.update", "reason": "not_found", "task_id": tid_int})
                            continue
                        responses.append(f"Updated task #{task.id}.")
                        metadata["executed"].append({"type": "todo.update", "task_id": task.id})

                elif a == "delete":
                    scope = (p.get("scope") or "").strip().lower()
                    if scope in {"all", "pending", "completed"}:
                        count = await crud.delete_tasks_bulk(user_id, scope=scope)
                        responses.append(f"Deleted {count} task(s).")
                        metadata["executed"].append({"type": "todo.delete.bulk", "count": count, "scope": scope})
                    else:
                        tid = p.get("id")
                        if not tid:
                            desc_q = p.get("description") or p.get("query") or p.get("title")
                            if not desc_q:
                                msg = "Couldn't delete task: no id or description provided."
                                responses.append(msg)
                                metadata_errors.append({"type": "todo.delete", "reason": "missing_identifier"})
                                continue
                            matches = await crud.find_tasks_by_description(user_id, str(desc_q))
                            if not matches:
                                msg = f"Couldn't find a task matching '{str(desc_q)}' to delete."
                                responses.append(msg)
                                metadata_errors.append({"type": "todo.delete", "reason": "not_found", "query": str(desc_q)})
                                continue
                            tid = matches[0].id
                        ok = await crud.delete_task(int(tid))
                        if not ok:
                            msg = f"Task #{int(tid)} wasn't found to delete."
                            responses.append(msg)
                            metadata_errors.append({"type": "todo.delete", "reason": "not_found", "task_id": int(tid)})
                            continue
                        responses.append(f"Deleted task #{int(tid)}.")
                        metadata["executed"].append({"type": "todo.delete", "task_id": int(tid)})

            elif t == "journal":
                if a == "create":
                    provided_entry = p.get("entry")
                    if not isinstance(provided_entry, str) or not provided_entry.strip():
                        logger.warning("journal.create: missing required entry parameter for user %s", user_id)
                        msg = "Could not create journal entry: missing content. Please provide what you'd like to journal."
                        responses.append(msg)
                        metadata_errors.append({"type": "journal.create", "reason": "missing_entry", "params": p})
                        continue
                    entry = provided_entry.strip()
                    logger.info("journal.create: using planner entry (len=%d)", len(entry))
                    j = await crud.create_journal(user_id, entry, None, None)
                    responses.append(f"Journal saved (id: {j.id}).")
                    metadata["executed"].append({"type": "journal.create", "journal_id": j.id})

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
                    metadata["executed"].append({"type": "journal.read", "total": len(js)})

                elif a == "update":
                    jid = p.get("id")
                    if not jid:
                        entry_q = p.get("entry") or p.get("summary")
                        if not entry_q:
                            msg = "Couldn't update journal: no id or entry text provided."
                            responses.append(msg)
                            metadata_errors.append({"type": "journal.update", "reason": "missing_identifier"})
                            continue
                        matches = await crud.find_journals_by_entry(user_id, str(entry_q))
                        if not matches:
                            msg = f"Couldn't find a journal matching the provided text to update."
                            responses.append(msg)
                            metadata_errors.append({"type": "journal.update", "reason": "not_found", "query": str(entry_q)})
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
                        metadata_errors.append({"type": "journal.update", "reason": "not_found", "journal_id": int(jid)})
                        continue
                    responses.append(f"Updated journal #{j.id}.")
                    metadata["executed"].append({"type": "journal.update", "journal_id": j.id})

                elif a == "delete":
                    scope = (p.get("scope") or "").strip().lower()
                    if scope in {"all"}:
                        count = await crud.delete_journals_bulk(user_id, scope=scope)
                        responses.append(f"Deleted {count} journal(s).")
                        metadata["executed"].append({"type": "journal.delete.bulk", "count": count, "scope": scope})
                    else:
                        jid = p.get("id")
                        if not jid:
                            entry_q = p.get("entry") or p.get("summary")
                            if not entry_q:
                                msg = "Couldn't delete journal: no id or entry text provided."
                                responses.append(msg)
                                metadata_errors.append({"type": "journal.delete", "reason": "missing_identifier"})
                                continue
                            matches = await crud.find_journals_by_entry(user_id, str(entry_q))
                            if not matches:
                                msg = f"Couldn't find a journal matching the provided text to delete."
                                responses.append(msg)
                                metadata_errors.append({"type": "journal.delete", "reason": "not_found", "query": str(entry_q)})
                                continue
                            jid = matches[0].id
                        ok = await crud.delete_journal(int(jid))
                        if not ok:
                            msg = f"Journal #{int(jid)} wasn't found to delete."
                            responses.append(msg)
                            metadata_errors.append({"type": "journal.delete", "reason": "not_found", "journal_id": int(jid)})
                            continue
                        responses.append(f"Deleted journal #{int(jid)}.")
                        metadata["executed"].append({"type": "journal.delete", "journal_id": int(jid)})

            elif t == "unknown":
                # Handle unrecognized text gracefully
                logger.info("execute_actions: encountered 'unknown' type for user %s, action=%s", user_id, a)
                original_text = p.get("original_text", "")
                error_detail = p.get("error", "")
                
                if a == "error":
                    msg = "I encountered an issue while processing your request. The planner couldn't understand the text format."
                    if error_detail:
                        logger.error("Planner error for user %s: %s", user_id, error_detail)
                else:
                    msg = "I couldn't determine if this should be a task or journal entry. Please be more specific, or try rephrasing your request."
                
                responses.append(msg)
                metadata_errors.append({
                    "type": "unknown",
                    "action": a,
                    "reason": "unrecognized_text",
                    "original_text": original_text[:200],  # truncate for safety
                    "error": error_detail if error_detail else None
                })
                continue

            else:
                # Gracefully handle truly unknown types (shouldn't happen after 'unknown' handling)
                logger.warning("execute_actions: unknown action type '%s' for user %s", t, user_id)
                msg = f"I couldn't understand the type of action requested (type: {t}). This text might not be meant for task or journal management."
                responses.append(msg)
                metadata_errors.append({"type": t, "action": a, "reason": "unsupported_type", "params": p})
                continue

        except Exception as e:
            # Never raise - convert all exceptions to soft errors
            logger.exception("Action execution failed for user %s, type=%s, action=%s: %s", user_id, t, a, e)
            msg = f"An error occurred while processing your request: {str(e)}"
            responses.append(msg)
            metadata_errors.append({
                "type": t or "unknown",
                "action": a or "unknown",
                "reason": "execution_exception",
                "error": str(e)
            })
            continue

    if not responses:
        reply = "Done."
    elif len(responses) == 1:
        reply = responses[0]
    else:
        reply = "Summary:\n\n" + "\n\n".join(responses)

    if metadata_errors:
        metadata["errors"] = metadata_errors

    return {"status": "ok", "message": reply, **metadata}


async def analyze_entry(entry: str):
    """Lightweight stub for journal analysis (sentiment, summary)."""
    return None, None
