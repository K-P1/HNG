import os
import asyncio
import logging
from typing import Any, Dict, List
from app.services import llm_service
from app.utils.telex_push import send_telex_followup

logger = logging.getLogger("services.telex")


async def process_telex_message(user_id: str, message: str) -> Dict[str, Any]:
    """Plan using strict schema and execute via llm_service executor."""
    text = (message or "").strip()
    logger.info("process_telex_message: received text='%s' (len=%d) for user_id=%s", text, len(text), user_id)
    plan = await llm_service.plan_actions(text)
    try:
        # Log the full planner output to aid debugging of fallbacks
        logger.info("process_telex_message: planner output: %s", plan)
    except Exception:
        # Avoid logging crashes if plan is not serializable
        logger.warning("process_telex_message: failed to log planner output (non-serializable)")
    actions: List[Dict[str, Any]] = plan.get("actions", []) if isinstance(plan, dict) else []
    if not actions:
        raise ValueError("Planner returned no actions")
    result = await llm_service.execute_actions(user_id, actions, text)
    return result


async def handle_a2a_request(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Main A2A entrypoint."""
    request_id = payload.get("id") or ""
    params = payload.get("params") or {}
    msg_obj = params.get("message") or {}
    parts = msg_obj.get("parts") if isinstance(msg_obj, dict) else None

    text = ""
    if isinstance(parts, list):
        # Collect top-level text parts
        texts = [str(p.get("text")) for p in parts if isinstance(p, dict) and p.get("text")]

        # Find the last nested data text (if any)
        last_nested_text = None
        for p in parts:
            if isinstance(p, dict) and isinstance(p.get("data"), list):
                for item in p["data"]:
                    if isinstance(item, dict) and item.get("text"):
                        last_nested_text = str(item.get("text"))

        # Build the final text: top-level texts + last nested text (if new)
        base_text = " ".join(texts).strip()
        if last_nested_text and last_nested_text.strip():
            if base_text:
                if last_nested_text not in base_text:
                    text = f"{base_text} {last_nested_text.strip()}".strip()
                else:
                    text = base_text
            else:
                text = last_nested_text.strip()
        else:
            text = base_text

        try:
            logger.info(
                "handle_a2a_request: built text from %d top-level part(s)%s -> '%s'",
                len(texts),
                ", with last nested data text appended" if last_nested_text else "",
                text,
            )
        except Exception:
            pass
    text = text or str(msg_obj.get("text") or params.get("text") or "")
    user_id = params.get("user_id") or msg_obj.get("user_id") or "unknown-user"

    push_config = params.get("configuration", {}).get("pushNotificationConfig", {}) or {}
    push_url = push_config.get("url")

    if push_url:
        preview = "Processing your request..."
        try:
            plan = await llm_service.plan_actions(text)
            acts = plan.get("actions", [])
            if isinstance(acts, list) and acts:
                labels = [str(a.get("type")) for a in acts if isinstance(a, dict) and a.get("type")]
                if labels:
                    preview = f"Planned steps: {', '.join(labels)}"
        except Exception:
            pass

        async def followup():
            try:
                result = await process_telex_message(user_id, text)
                msg = result.get("message") or "Done."
                # If we collected soft errors during execution, hint that some operations failed
                if isinstance(result, dict) and result.get("errors"):
                    msg = f"{msg}\n\nNote: Some steps couldn't be completed, but I finished the rest."
                await send_telex_followup(push_url, msg, push_config, request_id)
            except Exception as e:
                logger.exception("Follow-up failed: %s", e)
                await send_telex_followup(push_url, f"Error: {e}", push_config, request_id)

        # In tests, run follow-up inline to simplify synchronization; otherwise, schedule in background
        if os.getenv("PYTEST_CURRENT_TEST"):
            await followup()
        else:
            asyncio.create_task(followup())

        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {"messages": [{"role": "assistant", "content": preview}], "metadata": {"status": "processing"}},
        }

    result = await process_telex_message(user_id, text)
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "result": {"messages": [{"role": "assistant", "content": result.get('message', '')}], "metadata": result},
    }
