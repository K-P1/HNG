import httpx
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger("telex_push")


async def send_telex_followup(push_url: str, message: str, push_config: Optional[Dict[str, Any]] = None):
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

    payload = {
        "jsonrpc": "2.0",
        "id": "followup",
        "result": {
            "messages": [
                {"role": "assistant", "content": message}
            ]
        }
    }

    # Build headers (Authorization if provided)
    headers = {"Content-Type": "application/json"}
    scheme = "Bearer"
    token = None
    if push_config and isinstance(push_config, dict):
        token = push_config.get("token")
        auth = push_config.get("authentication")
        if isinstance(auth, dict):
            schemes = auth.get("schemes")
            if isinstance(schemes, list) and schemes:
                scheme = schemes[0] or scheme
    if token:
        headers["Authorization"] = f"{scheme} {token}"

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(push_url, json=payload, headers=headers)
            resp.raise_for_status()
            logger.info(f"Follow-up sent to Telex: {resp.status_code}")
    except Exception as e:
        logger.error(f"Failed to send follow-up to Telex: {e}")
