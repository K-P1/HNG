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
    """
    Send a follow-up message to Telex asynchronously.

    Used for long-running jobs where you want to send a second message
    after the initial response without blocking the main queue.

    Parameters
    ----------
    push_url : str
        The callback or webhook URL provided by Telex.
    message : str
        The follow-up message text to send.
    push_config : dict, optional
        Optional dict containing token or authentication info:
        {
            "url": str,
            "token": str,  # optional
            "authentication": { "schemes": ["Bearer"] }
        }
    request_id : str, optional
        Optional custom ID to correlate the message.
    """
    if not push_url:
        logger.info("send_telex_followup: no push URL provided, skipping.")
        return

    headers = {"Content-Type": "application/json"}
    token: Optional[str] = None

    # Prefer credentials nested under authentication per Telex guide; fallback to token
    if isinstance(push_config, dict):
        auth = push_config.get("authentication") or {}
        if isinstance(auth, dict):
            token = auth.get("credentials") or token
            schemes = auth.get("schemes") or []
            # If TelexApiKey is specified, use standard Bearer header
            if isinstance(schemes, list) and schemes and token:
                if schemes == ["TelexApiKey"]:
                    headers["Authorization"] = f"Bearer {token}"
                else:
                    # Default to Bearer even for other schemes unless specified otherwise
                    headers["Authorization"] = f"Bearer {token}"
        # Fallback legacy token field
        token = token or push_config.get("token")
        if token and "Authorization" not in headers:
            headers["Authorization"] = f"Bearer {token}"

    # Determine payload format by URL: Telex webhooks expect a JSON-RPC method call
    is_telex_webhook = ("/a2a/webhooks/" in push_url) or ("ping.telex.im" in push_url)

    if is_telex_webhook:
        payload = {
            "jsonrpc": "2.0",
            "id": request_id or str(uuid.uuid4()),
            "method": "message/send",
            "params": {
                "message": {
                    "kind": "message",
                    "messageId": str(uuid.uuid4()),
                    "role": "agent",
                    "parts": [{"kind": "text", "text": str(message)}],
                }
            },
        }
    else:
        # Generic webhook: return-style result envelope
        payload = {
            "jsonrpc": "2.0",
            "id": request_id or str(uuid.uuid4()),
            "result": {
                "messages": [
                    {
                        "role": "assistant",
                        "content": str(message),
                    }
                ]
            },
        }

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            logger.debug("Sending follow-up to %s", push_url)
            # For Telex webhooks, both Authorization: Bearer <token> and X-TELEX-API-KEY
            # are acceptable; we include Authorization and keep X-TELEX-API-KEY if legacy token provided
            if token and "X-TELEX-API-KEY" not in headers:
                headers["X-TELEX-API-KEY"] = str(token)

            resp = await client.post(push_url, json=payload, headers=headers)
            resp.raise_for_status()
            logger.info("Follow-up sent successfully (%s)", resp.status_code)
    except httpx.HTTPStatusError as he:
        # Include status and response body for clarity
        body = None
        try:
            body = resp.text
        except Exception:
            body = "<unavailable>"
        logger.error("Telex follow-up failed (%s): %s | body=%s", resp.status_code, he, body)
        raise
    except Exception as e:
        logger.error("Failed to send Telex follow-up: %s", e)
        raise
