import httpx
import logging

logger = logging.getLogger("telex_push")


async def send_telex_followup(push_url: str, message: str):
    """Send a follow-up message to Telex after the initial response."""
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

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(push_url, json=payload)
            resp.raise_for_status()
            logger.info(f"Follow-up sent to Telex: {resp.status_code}")
    except Exception as e:
        logger.error(f"Failed to send follow-up to Telex: {e}")
