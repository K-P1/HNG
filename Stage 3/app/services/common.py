import logging
from datetime import datetime
from typing import Any, Optional

logger = logging.getLogger("services.common")


def parse_dt(maybe: Any) -> Optional[datetime]:
    """Parse various datetime formats or return None if invalid."""
    if not maybe:
        return None

    if isinstance(maybe, datetime):
        return maybe

    if isinstance(maybe, (int, float)):
        try:
            return datetime.fromtimestamp(maybe)
        except Exception:
            return None

    if isinstance(maybe, str):
        for fmt in ("%Y-%m-%d", "%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%SZ"):
            try:
                return datetime.strptime(maybe, fmt)
            except Exception:
                continue
        try:
            import dateparser  # type: ignore
            return dateparser.parse(maybe)
        except Exception:
            return None

    return None


def format_tasks_list(tasks: list) -> str:
    """Create a readable summary of tasks."""
    if not tasks:
        return "You currently have no pending tasks."

    total = len(tasks)
    pending_count = sum(1 for t in tasks if getattr(t, "status", "pending") != "completed")
    header = f"Here are your tasks (total: {total}, pending: {pending_count}):"
    lines = [header, ""]

    def friendly(dt: Optional[datetime]) -> Optional[str]:
        if not dt:
            return None
        try:
            return dt.strftime("%b %d, %Y %I:%M %p")
        except Exception:
            return str(dt)

    for t in tasks:
        desc = getattr(t, "description", None) or str(t)
        status = getattr(t, "status", "pending")
        tid = getattr(t, "id", None)
        created = getattr(t, "created_at", None)
        due = getattr(t, "due_date", None)

        parts = [f"- {desc}", f"status: {status}"]
        if tid is not None:
            parts.append(f"id: {tid}")
        parts.append(f"created: {friendly(created) or 'N/A'}")
        if due:
            parts.append(f"due: {friendly(due)}")

        lines.append(" (".join([parts[0], ", ".join(parts[1:])]) + ")")

    lines.append("")
    lines.append("Tip: reply 'complete <id>' to mark a task as done.")
    return "\n".join(lines)
