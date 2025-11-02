import json
import os
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple


def _ensure_dir(path: str) -> None:
    directory = os.path.dirname(path)
    if directory and not os.path.exists(directory):
        os.makedirs(directory, exist_ok=True)


def get_telex_log_path() -> str:
    """Resolve the log file path for Telex traffic logs."""
    return os.getenv("TELEX_LOG_PATH", os.path.join("logs", "telex_traffic.jsonl"))


def get_telex_pretty_log_path() -> str:
    """Resolve the pretty (human-friendly) log file path."""
    return os.getenv("TELEX_PRETTY_LOG_PATH", os.path.join("logs", "telex_traffic_pretty.log"))


def json_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def safe_json_dump(obj: Any) -> str:
    """Serialize to JSON with sane defaults for non-serializable objects."""
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"), default=str)


def safe_json_dump_pretty(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=2, default=str)


def _truncate(text: Optional[str], max_len: int = 280) -> Optional[str]:
    if text is None:
        return None
    s = str(text)
    return s if len(s) <= max_len else s[: max_len - 1] + "…"


def _redact_sensitive(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Redact tokens and other sensitive fields from request payload."""
    data = deepcopy(payload)
    try:
        cfg = (
            data.get("params", {})
            .get("configuration", {})
            .get("pushNotificationConfig", {})
        )
        if isinstance(cfg, dict) and "token" in cfg:
            cfg["token"] = "***REDACTED***"
    except Exception:
        pass
    return data


def _summarize_request(payload: Dict[str, Any]) -> Dict[str, Any]:
    params = payload.get("params") if isinstance(payload, dict) else None
    message = params.get("message") if isinstance(params, dict) else None
    parts = message.get("parts") if isinstance(message, dict) else None
    text_parts = []
    has_data = False
    if isinstance(parts, list):
        for p in parts:
            if isinstance(p, dict):
                if p.get("kind") == "text" and p.get("text"):
                    text_parts.append(str(p.get("text")))
                if p.get("kind") == "data":
                    has_data = True
    text = " ".join(text_parts).strip()
    return {
        "id": payload.get("id"),
        "method": payload.get("method"),
        "user_id": (params.get("user_id") if isinstance(params, dict) else None),
        "message_preview": _truncate(text, 400),
        "parts_count": (len(parts) if isinstance(parts, list) else 0),
        "has_data_parts": has_data,
        "accepted_modes": (
            params.get("configuration", {}).get("acceptedOutputModes")
            if isinstance(params, dict)
            else None
        ),
        "push_url": (
            params.get("configuration", {})
            .get("pushNotificationConfig", {})
            .get("url")
            if isinstance(params, dict)
            else None
        ),
    }


def _summarize_response(resp: Dict[str, Any]) -> Dict[str, Any]:
    result = resp.get("result") if isinstance(resp, dict) else None
    messages = result.get("messages") if isinstance(result, dict) else None
    preview = None
    if isinstance(messages, list) and messages:
        first = messages[0]
        if isinstance(first, dict):
            preview = first.get("content") or first.get("text")
    return {
        "status": result.get("metadata", {}).get("status") if isinstance(result, dict) else None,
        "message_preview": _truncate(preview, 400),
        "message_count": len(messages) if isinstance(messages, list) else 0,
        "metadata_keys": list(result.get("metadata", {}).keys()) if isinstance(result, dict) else [],
    }


def log_telex_interaction_pretty(
    *,
    agent_name: str,
    path: str,
    method: str,
    request_id: Optional[str],
    client_host: Optional[str],
    request_payload: Dict[str, Any],
    response_payload: Dict[str, Any],
    status_code: int,
    latency_ms: float,
) -> None:
    """Write a human-friendly JSON block with summaries and redactions.

    Keeps the full (redacted) payloads under `request_raw` and `response_raw`,
    and provides concise summaries for quick scanning.
    """
    redacted_request = (
        _redact_sensitive(request_payload) if isinstance(request_payload, dict) else request_payload
    )
    summary = {
        "ts": json_now(),
        "agent": agent_name,
        "path": path,
        "method": method,
        "request_id": request_id,
        "client": client_host,
        "latency_ms": round(float(latency_ms), 3),
        "status": int(status_code),
        "request": _summarize_request(redacted_request) if isinstance(redacted_request, dict) else None,
        "response": _summarize_response(response_payload) if isinstance(response_payload, dict) else None,
        "request_raw": redacted_request,
        "response_raw": response_payload,
    }

    log_path = get_telex_pretty_log_path()
    _ensure_dir(log_path)
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(safe_json_dump_pretty(summary))
        f.write("\n\n")
