import os
import asyncio
import logging
from typing import Any, Dict, List
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


async def process_telex_message(user_id: str, message: str) -> Dict[str, Any]:
    """Plan using strict schema and execute via llm_service executor."""
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
    text = latest_text(msg_obj.get("parts")) or msg_obj.get("text") or params.get("text") or ""
    text = str(text).strip()
    user_id = params.get("user_id") or msg_obj.get("user_id") or "unknown-user"

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
