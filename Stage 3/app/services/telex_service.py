"""
Telex service: handles A2A protocol requests
Flow: extract text → plan actions → execute → respond
"""
import os
import asyncio
import logging
import re
from typing import Any, Dict, List, Optional
from uuid import uuid4
from app.services import llm_service
from app.utils.telex_push import send_telex_followup
from app.utils.a2a_helpers import build_task_result
import app.models.a2a as a2a_models

logger = logging.getLogger("services.telex")


def _extract_text(payload: Dict[str, Any]) -> str:
    """
    Extract user message text from A2A payload.
    Extracts only parts[1].data[-1].text (latest user message from conversation history).
    Falls back to parts[0].text if parts[1] doesn't exist.
    """
    params = payload.get("params", {})
    msg_obj = params.get("message", {})
    parts = msg_obj.get("parts") if isinstance(msg_obj, dict) else None
    
    # Extract parts[1].data[-1] text (latest user message from conversation history)
    if isinstance(parts, list) and len(parts) > 1:
        second = parts[1]
        if isinstance(second, dict) and second.get("kind") == "data":
            data = second.get("data")
            if isinstance(data, list) and data:
                # Get the last item in the data array
                last_item = data[-1]
                if isinstance(last_item, dict) and last_item.get("kind") == "text":
                    hist_text = last_item.get("text", "")
                    if isinstance(hist_text, str) and hist_text.strip():
                        return hist_text.strip()
    
    # Fallback: Extract parts[0] text (for simple payloads or when parts[1] is unavailable)
    if isinstance(parts, list) and len(parts) > 0:
        first = parts[0]
        if isinstance(first, dict) and first.get("kind") == "text":
            text = first.get("text", "")
            if isinstance(text, str) and text.strip():
                return text.strip()
    
    # Final fallback to message.text or params.text
    text = msg_obj.get("text") or params.get("text") or ""
    return str(text).strip()


def _normalize_text(text: str) -> str:
    """Remove HTML tags and normalize whitespace."""
    if not text:
        return ""
    # Remove <p>, </p>, <br> tags
    text = re.sub(r"<\s*/?\s*p\s*>|<\s*br\s*/?\s*>", "\n", text, flags=re.IGNORECASE)
    # Collapse whitespace
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return "\n".join(lines)


async def process_telex_message(user_id: str, message: str) -> Dict[str, Any]:
    """Plan and execute actions from user message."""
    text = _normalize_text(message)
    
    if not text:
        return {
            "status": "ok",
            "message": "Please send a task or journal entry.",
            "executed": [],
            "errors": [{"type": "empty_input"}],
        }

    # Plan actions
    try:
        # Call LLM service to plan actions
        plan = await llm_service.plan_actions(text)
        actions = plan.get("actions", [])
    except Exception as e:
        logger.warning("Planning failed: %s", e)
        return {
            "status": "ok",
            "message": "I couldn't understand your message.",
            "executed": [],
            "errors": [{"type": "planning_failed", "detail": str(e)}],
        }

    if not actions:
        return {
            "status": "ok",
            "message": "I couldn't detect any actionable steps.",
            "executed": [],
            "errors": [{"type": "no_actions"}],
        }

    # Execute actions
    return await llm_service.execute_actions(user_id, actions)


async def handle_a2a_request(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Main A2A request handler."""
    request_id = payload.get("id", "")
    params = payload.get("params", {})
    
    # Extract text and user_id
    text = _extract_text(payload)
    msg_obj = params.get("message", {})
    user_id = params.get("user_id") or msg_obj.get("user_id") or "unknown-user"
    
    # Configuration
    config = params.get("configuration", {})
    push_config = config.get("pushNotificationConfig") or {}
    push_url = push_config.get("url")
    
    # Determine blocking mode
    # override default blocking with .env async option. restore when Telex fix followups
    #req_blocking = config.get("blocking", True)
    async_enabled = os.getenv("A2A_ASYNC_ENABLED", "").lower() in ("true", "1", "yes")
    blocking = not async_enabled
    
    context_id = params.get("contextId") or str(uuid4())
    user_msg = a2a_models.A2AMessage(role="user", parts=[a2a_models.MessagePart(kind="text", text=text)])

    # Async mode: return preview, process in background
    if push_url and not blocking:
        # Quick plan preview
        preview = "Processing your request..."
        try:
            plan = await llm_service.plan_actions(text)
            actions = plan.get("actions", [])
            types = [a["type"] for a in actions if isinstance(a, dict) and a.get("type")]
            if types:
                preview = f"Planned steps: {', '.join(types)}"
        except Exception:
            pass

        # Background processing
        async def followup():
            try:
                # Do the actual work
                result = await process_telex_message(user_id, text)
                msg = result.get("message", "Done.")
                if result.get("errors"):
                    msg += "\n\nNote: Some steps couldn't be completed."
                
                # Prepare task data if available
                parts = []
                if result.get("task_list"):
                    parts.append({"kind": "data", "data": {"tasks": result["task_list"]}})
                
                # Send result back to Telex via webhook
                await send_telex_followup(push_url, msg, push_config, request_id, additional_parts=parts)
            except Exception as e:
                logger.exception("Follow-up failed: %s", e)
                # Try to send error notification, but don't fail if this also errors
                try:
                    await send_telex_followup(push_url, f"Error: {e}", push_config, request_id)
                except Exception as e2:
                    logger.error("Failed to send error notification: %s", e2)

        # Run in background (or sync for tests)
        if os.getenv("PYTEST_CURRENT_TEST"):
            await followup()
        else:
            # Task Execution
            asyncio.create_task(followup())

        return build_task_result(request_id, context_id, "working", preview, history_msgs=[user_msg])

    # Sync mode: process and return complete result
    try:
        result = await process_telex_message(user_id, text)
        
        artifacts = [
            {"name": "assistantResponse", "parts": [{"kind": "text", "text": result.get("message", "")}]},
            {"name": "ExecutionResults", "parts": [{"kind": "data", "data": {
                "executed": result.get("executed", []),
                "errors": result.get("errors", []),
            }}]},
        ]
        
        if result.get("task_list"):
            artifacts.append({"name": "ToolResults", "parts": [{"kind": "data", "data": {"tasks": result["task_list"]}}]})

        return build_task_result(request_id, context_id, "completed", result.get("message", ""), artifacts, [user_msg])

    except Exception as e:
        logger.exception("Request failed: %s", e)
        return build_task_result(
            request_id, context_id, "failed", f"Error: {e}",
            artifacts=[{"name": "Error", "parts": [{"kind": "data", "data": {"detail": str(e)}}]}],
            history_msgs=[user_msg]
        )
