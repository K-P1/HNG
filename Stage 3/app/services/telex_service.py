import os
import asyncio
import logging
from typing import Any, Dict, List, Optional
from uuid import uuid4
from app.services import llm_service
from app.utils.telex_push import send_telex_followup
from app.utils.a2a_helpers import (
    latest_text,
    parse_bool_env,
    build_task_result,
)
import app.models.a2a as a2a_models

logger = logging.getLogger("services.telex")


def _normalize_text(s: Optional[str]) -> str:
    """Normalize text by trimming and removing trivial HTML wrappers."""
    if not isinstance(s, str):
        return ""
    txt = s.strip()
    if not txt:
        return ""
    try:
        import re

        # Remove simple paragraph wrappers and line breaks
        txt = re.sub(r"\s*<\s*/?\s*p\s*>\s*", "\n", txt, flags=re.IGNORECASE)
        txt = re.sub(r"<\s*br\s*/?\s*>", "\n", txt, flags=re.IGNORECASE)

        # Collapse and clean lines
        lines = [line.strip() for line in txt.splitlines()]
        lines = [line for line in lines if line]
        txt = "\n".join(lines)
    except Exception:
        # Keep best-effort text rather than crashing
        pass
    return txt.strip()


def prepare_combined_message(primary_text: Optional[str], fallback_text: Optional[str]) -> Dict[str, Any]:
    """Return a normalized combined view of primary and fallback text.

    Result keys:
      - primary_text: normalized primary ("" if none)
      - latest_text: normalized fallback ("" if none)
      - same: whether both non-empty and identical
      - final_text: if same -> string; else -> dict with both texts (keeps routing hint)
    """
    p = _normalize_text(primary_text or "")
    f = _normalize_text(fallback_text or "")
    same = bool(p) and (p == f)
    if same:
        return {"primary_text": p, "latest_text": f, "same": True, "final_text": p}
    return {"primary_text": p, "latest_text": f, "same": False, "final_text": {"primary_text": p, "latest_text": f}}



async def process_telex_message(user_id: str, message: str) -> Dict[str, Any]:
    """Plan using strict schema and execute via llm_service executor."""
    # Safety check: handle dict input (shouldn't happen after fix, but defensive)
    if isinstance(message, dict):
        logger.warning("process_telex_message: received dict instead of string, extracting text")
        message = message.get("primary_text") or message.get("latest_text") or ""
    
    text = (message or "").strip()
    logger.info("process_telex_message: received text='%s' (len=%d) for user_id=%s", text, len(text), user_id)

    if not text:
        return {
            "status": "ok",
            "message": "I didn't receive any text. Please send a task or a journal entry so I can help.",
            "executed": [],
            "errors": [{"type": "planner", "reason": "empty_input"}],
        }

    try:
        plan = await llm_service.plan_actions(text)
        logger.debug("planner output: %s", plan)
    except Exception as e:
        logger.warning("planning failed: %s", e)
        return {
            "status": "ok",
            "message": "I couldn't understand any actionable steps from your message.",
            "executed": [],
            "errors": [{"type": "planner", "reason": "planning_failed", "detail": str(e)}],
        }

    actions = plan.get("actions", []) if isinstance(plan, dict) else []
    if not actions:
        return {
            "status": "ok",
            "message": "I couldn't detect any actionable steps from your message.",
            "executed": [],
            "errors": [{"type": "planner", "reason": "no_actions"}],
        }

    try:
        return await llm_service.execute_actions(user_id, actions, text)
    except Exception as e:
        logger.warning("execution failed: %s", e)
        return {
            "status": "ok",
            "message": "I ran into an error executing the planned steps.",
            "executed": [],
            "errors": [{"type": "executor", "reason": "execution_failed", "detail": str(e)}],
        }


async def handle_a2a_request(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Main A2A entrypoint."""
    request_id = payload.get("id", "")
    params = payload.get("params", {})
    msg_obj = params.get("message", {})
    parts = msg_obj.get("parts") if isinstance(msg_obj, dict) else None

    # Primary top-level text (parts[0]) if present and a text kind
    primary_text = ""
    if isinstance(parts, list) and parts:
        first = parts[0]
        if isinstance(first, dict) and first.get("kind") == "text":
            t0 = first.get("text")
            if isinstance(t0, str) and t0.strip():
                primary_text = t0

    fallback_text = latest_text(parts) or msg_obj.get("text") or params.get("text") or ""
    fallback_text = str(fallback_text).strip()
    user_id = params.get("user_id") or msg_obj.get("user_id") or "unknown-user"

    combined = prepare_combined_message(primary_text, fallback_text)
    logger.debug("telex: primary_len=%d fallback_len=%d same=%s",
                 len(combined["primary_text"]), len(combined["latest_text"]), combined["same"])
    # Final text to process
    # Extract text string from combined result
    final_text = combined["final_text"]
    if isinstance(final_text, dict):
        # When texts differ, final_text is a dict - concatenate both or use latest_text (which is the most recent user message)
        primary = final_text.get("primary_text", "").strip()
        latest = final_text.get("latest_text", "").strip()
        # Concatenate if both exist, otherwise use whichever is available
        if primary and latest:
            text = f"{primary} {latest}"
        else:
            text = latest or primary or ""
    else:
        # When texts are same, final_text is a string
        text = final_text or ""

    config = params.get("configuration", {}) if isinstance(params, dict) else {}
    push_config = config.get("pushNotificationConfig", {}) or {}
    push_url = push_config.get("url")
    req_blocking = bool(config.get("blocking", True))

    env_bool = parse_bool_env(os.getenv("A2A_ASYNC_ENABLED"))
    blocking = (
        req_blocking if env_bool is None
        else True if env_bool is False
        else req_blocking is True
    )

    context_id = params.get("contextId") or str(uuid4())

    if push_url and not blocking:
        preview = "Processing your request..."
        planned_labels: List[str] = []

        try:
            plan = await llm_service.plan_actions(text)
            actions = plan.get("actions", [])
            if isinstance(actions, list):
                planned_labels = [a["type"] for a in actions if isinstance(a, dict) and isinstance(a.get("type"), str)]
                if planned_labels:
                    preview = f"Planned steps: {', '.join(planned_labels)}"
        except Exception:
            pass

        async def followup():
            try:
                result = await process_telex_message(user_id, text)
                msg = result.get("message") or "Done."
                if result.get("errors"):
                    msg += "\n\nNote: Some steps couldn't be completed."
                parts = []
                if isinstance(result.get("task_list"), list):
                    parts.append({"kind": "data", "data": {"name": "ToolResults", "tasks": result["task_list"]}})
                await send_telex_followup(push_url, msg, push_config, request_id, additional_parts=parts)
            except Exception as e:
                logger.exception("Follow-up failed: %s", e)
                await send_telex_followup(push_url, f"Error: {e}", push_config, request_id)

        if os.getenv("PYTEST_CURRENT_TEST"):
            await followup()
        else:
            asyncio.create_task(followup())

        history = [a2a_models.A2AMessage(role="user", parts=[a2a_models.MessagePart(kind="text", text=text)])]
        return build_task_result(
            request_id,
            context_id,
            "working",
            preview,
            artifacts=[{"name": "PlanPreview", "parts": [{"kind": "data", "data": {"planned": planned_labels}}]}],
            history_msgs=history,
        )

    try:
        result = await process_telex_message(user_id, text)

        artifacts = [
            {"name": "assistantResponse", "parts": [{"kind": "text", "text": str(result.get("message", ""))}]},
            {
                "name": "ExecutionResults",
                "parts": [{"kind": "data", "data": {
                    "executed": result.get("executed", []),
                    "errors": result.get("errors", []),
                    "status": result.get("status", "ok"),
                }}],
            },
        ]
        if isinstance(result.get("task_list"), list):
            artifacts.append({"name": "ToolResults", "parts": [{"kind": "data", "data": {"tasks": result["task_list"]}}]})

        history = [a2a_models.A2AMessage(role="user", parts=[a2a_models.MessagePart(kind="text", text=text)])]
        return build_task_result(request_id, context_id, "completed", str(result.get("message", "")), artifacts, history)

    except Exception as e:
        logger.exception("handle_a2a_request: failed: %s", e)
        return build_task_result(
            request_id,
            context_id,
            "failed",
            f"Error processing request: {e}",
            artifacts=[{"name": "Error", "parts": [{"kind": "data", "data": {"type": "internal", "detail": str(e)}}]}],
            history_msgs=[a2a_models.A2AMessage(role="user", parts=[a2a_models.MessagePart(kind="text", text=text)])],
        )
