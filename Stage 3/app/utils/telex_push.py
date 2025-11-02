import httpx
import uuid
import json
import logging
from typing import Optional, Dict, Any, List

logger = logging.getLogger("telex_push")


async def send_telex_followup(
    push_url: str,
    message: str,
    push_config: Optional[Dict[str, Any]] = None,
    request_id: Optional[str] = None,
    *,
    additional_parts: Optional[List[Dict[str, Any]]] = None,
) -> None:
    """
    Send an asynchronous follow-up message to Telex.

    Used for long-running jobs where you want to send a message
    after the initial response without blocking the main queue.
    """
    if not push_url:
        logger.info("No push URL provided — skipping follow-up.")
        return

    headers = {"Content-Type": "application/json"}
    token = _extract_token(push_config)

    if token:
        headers["Authorization"] = f"Bearer {token}"
        headers["X-TELEX-API-KEY"] = str(token)

    is_telex_webhook = "/a2a/webhooks/" in push_url or "ping.telex.im" in push_url

    payload = (
        _telex_payload(message, additional_parts, request_id)
        if is_telex_webhook
        else _generic_payload(message, request_id)
    )

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            logger.debug("Sending follow-up to %s", push_url)
            resp = await client.post(push_url, json=payload, headers=headers)
            resp.raise_for_status()
            logger.info("Follow-up sent successfully (%s)", resp.status_code)

    except httpx.HTTPStatusError as he:
        logger.warning(
            "Follow-up failed (%s). Retrying with minimal payload...",
            he.response.status_code,
        )
        if is_telex_webhook:
            await _retry_minimal_telex(client, push_url, message, headers, request_id)
        else:
            _log_error(resp, he)
            raise
    except Exception as e:
        logger.error("Failed to send Telex follow-up: %s", e)
        raise


def _extract_token(push_config: Optional[Dict[str, Any]]) -> Optional[str]:
    """Extract token from Telex push_config, supporting both legacy and new formats."""
    if not isinstance(push_config, dict):
        return None

    auth = push_config.get("authentication", {})
    if isinstance(auth, dict):
        token = auth.get("credentials")
        if token:
            return token
    return push_config.get("token")


def _as_part_list(message: str, extras: Optional[List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    """Convert message + extras into Telex 'parts' schema."""
    parts = [{"kind": "text", "text": str(message), "metadata": None}]
    if not extras:
        return parts

    for p in extras:
        if not isinstance(p, dict):
            continue

        kind = p.get("kind")
        if kind == "text" and p.get("text") is not None:
            parts.append({"kind": "text", "text": str(p["text"]), "metadata": None})
        elif kind == "data":
            try:
                data_str = json.dumps(p.get("data")) if p.get("data") is not None else "null"
            except Exception:
                data_str = json.dumps({"value": str(p.get("data"))})
            parts.append({"kind": "text", "text": data_str, "metadata": None})
        elif kind == "file":
            url = p.get("file_url") or p.get("url")
            if url:
                parts.append({"kind": "text", "text": str(url), "metadata": None})
        else:
            parts.append({"kind": "text", "text": str(p), "metadata": None})

    return parts


def _telex_payload(message: str, extras: Optional[List[Dict[str, Any]]], request_id: Optional[str]) -> Dict[str, Any]:
    """Construct Telex webhook JSON-RPC payload."""
    return {
        "jsonrpc": "2.0",
        "id": request_id or str(uuid.uuid4()),
        "method": "message/send",
        "params": {
            "message": {
                "kind": "message",
                "messageId": str(uuid.uuid4()),
                "role": "agent",
                "parts": _as_part_list(message, extras),
                "contextId": None,
                "taskId": None,
            },
            "metadata": None,
        },
    }


def _generic_payload(message: str, request_id: Optional[str]) -> Dict[str, Any]:
    """Construct a generic webhook payload."""
    return {
        "jsonrpc": "2.0",
        "id": request_id or str(uuid.uuid4()),
        "result": {
            "messages": [{"role": "assistant", "content": str(message)}],
        },
    }


async def _retry_minimal_telex(client: httpx.AsyncClient, url: str, message: str, headers: Dict[str, str], request_id: Optional[str]) -> None:
    """Fallback retry for Telex webhook with minimal payload."""
    minimal_payload = _telex_payload(message, None, request_id)
    resp2 = await client.post(url, json=minimal_payload, headers=headers)
    resp2.raise_for_status()
    logger.info("Follow-up (minimal) sent successfully (%s)", resp2.status_code)


def _log_error(resp: Optional[httpx.Response], error: Exception) -> None:
    """Log detailed error info safely."""
    body = getattr(resp, "text", "<unavailable>") if resp else "<no response>"
    logger.error("Telex follow-up failed: %s | body=%s", error, body)
