import httpx
import uuid
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger("telex_push")


async def send_telex_followup(
    push_url: str,
    message: str,
    push_config: Optional[Dict[str, Any]] = None,
    request_id: Optional[str] = None,
) -> None:
    """Send a follow-up message to Telex after the initial response.

    If push_config contains authentication details, include Authorization header.
    Expected shape (from Telex):
    {
        "url": str,
        "token": str,                               # optional bearer token
        "authentication": { "schemes": ["Bearer"] }  # optional scheme list
    }
    """
    if not push_url:
        logger.warning("No push URL provided; cannot send follow-up.")
        return

    # Build headers (Authorization and/or X-TELEX-API-KEY if provided)
    headers = {"Content-Type": "application/json"}
    scheme = "Bearer"
    token = None
    try:
        if push_config and isinstance(push_config, dict):
            token = push_config.get("token")
            auth = push_config.get("authentication")
            if isinstance(auth, dict):
                schemes = auth.get("schemes")
                if isinstance(schemes, list) and schemes:
                    scheme = schemes[0] or scheme
    except Exception:
        token = None

    # Prefer Telex API key header if a token is provided
    if token:
        headers["X-TELEX-API-KEY"] = str(token)
        if scheme:
            headers["Authorization"] = f"{scheme} {token}"
    logger.debug(
        "Telex follow-up auth prepared: scheme=%s, token_present=%s, x_api=%s",
        scheme,
        bool(token),
        "set" if headers.get("X-TELEX-API-KEY") else "unset",
    )

    is_telex_webhook = "/a2a/webhooks/" in (push_url or "")
    if is_telex_webhook:
        # Telex expects a JSON-RPC 2.0 payload with method "message/send"
        payload = {
            "jsonrpc": "2.0",
            "id": request_id or str(uuid.uuid4()),
            "method": "message/send",
            "params": {
                # Telex requires a top-level kind within params
                "kind": "message",
                "message": {
                    # Required by Telex: unique message id
                    "messageId": str(uuid.uuid4()),
                    # Role must be one of "user" | "agent"
                    "role": "agent",
                    "parts": [
                        {"kind": "text", "text": str(message)}
                    ],
                }
            },
        }
    else:
        payload = {
            "jsonrpc": "2.0",
            "id": request_id or "followup",
            "result": {
                "messages": [
                    {"role": "assistant", "content": str(message)}
                ]
            }
        }

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            logger.debug("Sending Telex follow-up to %s with payload=%s", push_url, payload)
            resp = await client.post(push_url, json=payload, headers=headers)
            try:
                resp.raise_for_status()
            except httpx.HTTPStatusError as he:
                # Include body in logs to help diagnose 4xx payload issues
                body = None
                try:
                    body = resp.json()
                except Exception:
                    try:
                        body = resp.text
                    except Exception:
                        body = "<unavailable>"
                logger.error("Telex follow-up failed: %s | response=%s", he, body)
                raise
            logger.info(f"Follow-up sent to Telex: {resp.status_code}")
    except Exception as e:
        logger.error(f"Failed to send follow-up to Telex: {e}")
