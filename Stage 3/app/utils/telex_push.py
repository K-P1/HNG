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
    """Send asynchronous follow-up message to Telex."""
    if not push_url:
        return

    # Prepare headers with authentication
    headers = {"Content-Type": "application/json"}
    token = _extract_token(push_config)
    if token:
        headers["Authorization"] = f"Bearer {token}"
        headers["X-TELEX-API-KEY"] = str(token)

    # Build payload
    is_telex = "/a2a/webhooks/" in push_url or "ping.telex.im" in push_url
    payload = _telex_payload(message, additional_parts, request_id) if is_telex else _generic_payload(message, request_id)

    # Send request
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(push_url, json=payload, headers=headers)
            resp.raise_for_status()
            logger.info("Follow-up sent (%s)", resp.status_code)
    except httpx.HTTPStatusError as e:
        logger.warning("Follow-up failed (%s), retrying minimal...", e.response.status_code)
        if is_telex:
            async with httpx.AsyncClient(timeout=10) as client:
                minimal = _telex_payload(message, None, request_id)
                resp = await client.post(push_url, json=minimal, headers=headers)
                resp.raise_for_status()
        else:
            raise
    except Exception as e:
        logger.error("Follow-up error: %s", e)
        raise


def _extract_token(push_config: Optional[Dict[str, Any]]) -> Optional[str]:
    """Extract authentication token from push config."""
    if not isinstance(push_config, dict):
        return None
    
    # Try authentication.credentials first
    auth = push_config.get("authentication", {})
    if isinstance(auth, dict):
        token = auth.get("credentials")
        if token:
            return token
    
    # Fallback to top-level token
    return push_config.get("token")


def _as_part_list(message: str, extras: Optional[List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    """Convert message and extras into Telex parts."""
    parts = [{"kind": "text", "text": str(message), "metadata": None}]
    
    if extras:
        for p in extras:
            if not isinstance(p, dict):
                continue
            kind = p.get("kind")
            if kind == "text":
                parts.append({"kind": "text", "text": str(p.get("text", "")), "metadata": None})
            elif kind == "data":
                data_str = json.dumps(p.get("data")) if p.get("data") else "null"
                parts.append({"kind": "text", "text": data_str, "metadata": None})
            elif kind == "file" and (p.get("file_url") or p.get("url")):
                parts.append({"kind": "text", "text": str(p.get("file_url") or p.get("url")), "metadata": None})
    
    return parts


def _telex_payload(message: str, extras: Optional[List[Dict[str, Any]]], request_id: Optional[str]) -> Dict[str, Any]:
    """Build Telex JSON-RPC payload."""
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
            },
        },
    }


def _generic_payload(message: str, request_id: Optional[str]) -> Dict[str, Any]:
    """Build generic webhook payload."""
    return {
        "jsonrpc": "2.0",
        "id": request_id or str(uuid.uuid4()),
        "result": {"messages": [{"role": "assistant", "content": str(message)}]},
    }
