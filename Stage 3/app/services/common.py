import logging
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger("services.common")


def parse_dt(maybe: Any) -> Optional[datetime]:
    """Parse various datetime formats and return timezone-aware datetime in UTC."""
    if not maybe:
        return None

    if isinstance(maybe, datetime):
        # If already timezone-aware, return as-is; otherwise make it UTC
        if maybe.tzinfo is not None:
            return maybe
        return maybe.replace(tzinfo=timezone.utc)

    if isinstance(maybe, (int, float)):
        try:
            # fromtimestamp with timezone argument returns timezone-aware datetime
            return datetime.fromtimestamp(maybe, tz=timezone.utc)
        except Exception:
            return None

    if isinstance(maybe, str):
        for fmt in ("%Y-%m-%d", "%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%SZ"):
            try:
                dt = datetime.strptime(maybe, fmt)
                # Make timezone-aware (assume UTC if no timezone specified)
                return dt.replace(tzinfo=timezone.utc)
            except Exception:
                continue
        try:
            import dateparser  # type: ignore
            # Parse with timezone-aware settings
            # Use PREFER_DATES_FROM='future' for relative dates like "in 5 minutes"
            dt = dateparser.parse(
                maybe, 
                settings={
                    'TIMEZONE': 'UTC',  # Parse all dates as UTC
                    'RETURN_AS_TIMEZONE_AWARE': True,
                    'PREFER_DATES_FROM': 'future'
                }
            )
            if dt:
                # Convert to UTC if not already
                if dt.tzinfo != timezone.utc:
                    dt = dt.astimezone(timezone.utc)
                return dt
        except Exception as e:
            logger.debug(f"Dateparser failed for '{maybe}': {e}")
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
