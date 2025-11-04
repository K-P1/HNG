from typing import Any, Dict, List, Optional, Literal
from uuid import uuid4
import app.models.a2a as a2a_models


def latest_text(parts: Optional[List[Any]]) -> str:
    """Extract latest textual content from A2A message parts.

    Works by walking parts in reverse order, preferring:
      1) last 'text' part
      2) last textual entry inside a 'data' part list
    Returns "" if nothing found.
    """
    if not parts:
        return ""
    for p in reversed(parts):
        if not isinstance(p, dict):
            continue
        kind = p.get("kind")
        text = p.get("text")
        if kind == "text" and isinstance(text, str) and text.strip():
            return text.strip()
        if kind == "data" and isinstance(p.get("data"), list):
            for item in reversed(p["data"]):
                if isinstance(item, dict):
                    t = item.get("text")
                    if isinstance(t, str) and t.strip():
                        return t.strip()
    return ""


def parse_bool_env(val: Optional[str]) -> Optional[bool]:
    """Parse an env string into a boolean or None."""
    if not val:
        return None
    s = str(val).strip().lower()
    if s in {"true", "1", "yes"}:
        return True
    if s in {"false", "0", "no"}:
        return False
    return None


def as_message_part(p: Dict[str, Any]) -> a2a_models.MessagePart:
    return a2a_models.MessagePart(
        kind=p.get("kind", "text"),
        text=p.get("text"),
        data=p.get("data"),
        file_url=p.get("file_url"),
    )


def build_artifacts(artifacts: Optional[List[Dict[str, Any]]]) -> List[a2a_models.Artifact]:
    """Convert arbitrary artifact dicts into validated A2A Artifact objects."""
    result = []
    if not artifacts:
        return result

    for art in artifacts:
        if isinstance(art, a2a_models.Artifact):
            result.append(art)
            continue
        try:
            parts = [as_message_part(p) for p in art.get("parts", []) or []]
            result.append(a2a_models.Artifact(name=art.get("name", "artifact"), parts=parts))
        except Exception:
            result.append(
                a2a_models.Artifact(name="artifact", parts=[a2a_models.MessagePart(kind="text", text=str(art))])
            )
    return result


def build_task_result(
    request_id: str,
    context_id: str,
    state: Literal["working", "completed", "input-required", "failed"],
    message_text: str,
    artifacts: Optional[List[Dict[str, Any]]] = None,
    history_msgs: Optional[List[a2a_models.A2AMessage]] = None,
) -> Dict[str, Any]:
    """Return a fully A2A-compliant TaskResult envelope."""
    status_message = a2a_models.A2AMessage(role="agent", parts=[a2a_models.MessagePart(kind="text", text=message_text)])
    task = a2a_models.TaskResult(
        id=str(uuid4()),
        contextId=context_id,
        status=a2a_models.TaskStatus(state=state, message=status_message),
        artifacts=build_artifacts(artifacts),
        history=history_msgs or [],
    )
    return {"jsonrpc": "2.0", "id": request_id, "result": task.model_dump()}
