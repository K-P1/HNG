import logging
import os
import json
from typing import Any, Dict, List

logger = logging.getLogger("llm")
# Don't add handler - use the root logger's handler to avoid duplicates
logger.setLevel(logging.INFO)


def _require_env():
    if os.getenv("LLM_PROVIDER", "").lower() != "groq":
        logger.error("LLM_PROVIDER must be 'groq'")
        raise RuntimeError("LLM_PROVIDER must be 'groq'")
    if not os.getenv("GROQ_API_KEY"):
        logger.error("GROQ_API_KEY is not configured")
        raise RuntimeError("GROQ_API_KEY is not configured")


def _get_groq_client():
    # Lazy import so tests can run without groq installed if desired
    try:
        from groq import Groq  # type: ignore
    except Exception as e:
        logger.exception("Failed to import groq client: %s", e)
        raise
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        logger.error("GROQ_API_KEY is not configured")
        raise RuntimeError("GROQ_API_KEY is not configured")
    logger.debug("Groq client initialized.")
    return Groq(api_key=api_key)


def _groq_chat(messages: List[Dict[str, str]], *, response_json: bool = False,
               temperature: float = 0.2, max_tokens: int = 256) -> str:
    """
    Minimal wrapper around Groq chat completion.
    When response_json=True we request a JSON object response via response_format.
    This function returns the raw content string (may be JSON text).
    """
    _require_env()
    client = _get_groq_client()
    model = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
    kwargs = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if response_json:
        kwargs["response_format"] = {"type": "json_object"}
    logger.debug("Sending chat request to Groq: model=%s, temperature=%s", model, temperature)
    resp = client.chat.completions.create(**kwargs)
    if not resp or not getattr(resp, "choices", None):
        logger.error("Groq returned no choices")
        raise RuntimeError("Groq returned no choices")
    content = resp.choices[0].message.content
    if not content:
        logger.error("Groq returned empty content")
        raise RuntimeError("Groq returned empty content")
    logger.debug("Groq response received.")
    return content


def _validate_action_shape(action: Dict[str, Any]) -> None:
    """
    Raises RuntimeError if action does not conform to the strict schema:
    {
      "type": "todo" | "journal",
      "action": "create" | "read" | "update" | "delete",
      "params": dict
    }
    """
    if not isinstance(action, dict):
        raise RuntimeError("Each action must be an object")
    t = action.get("type")
    a = action.get("action")
    p = action.get("params")
    if t not in {"todo", "journal", "unknown"}:
        raise RuntimeError(f"Action 'type' must be 'todo', 'journal', or 'unknown', got: {t!r}")
    
    # Unknown type only accepts 'none' action
    if t == "unknown":
        if a not in {"none", None}:
            raise RuntimeError(f"Action type 'unknown' must have action 'none', got: {a!r}")
        action["action"] = "none"  # Normalize
        action["params"] = {}
        return  # Skip further validation
    
    if a not in {"create", "read", "update", "delete"}:
        raise RuntimeError(f"Action 'action' must be one of create/read/update/delete, got: {a!r}")
    if p is None:
        action["params"] = {}
    elif not isinstance(p, dict):
        raise RuntimeError("Action 'params' must be a JSON object")

    # Stricter per-action validation
    p = action.get("params", {})
    if t == "todo" and a == "create":
        desc = p.get("description")
        if not isinstance(desc, str) or not desc.strip():
            raise RuntimeError("todo.create requires params.description (non-empty string)")
        # Optional due/due_date must be string if present
        if "due" in p and p.get("due") is not None and not isinstance(p.get("due"), str):
            raise RuntimeError("todo.create params.due must be a string if provided")
        if "due_date" in p and p.get("due_date") is not None and not isinstance(p.get("due_date"), str):
            raise RuntimeError("todo.create params.due_date must be a string if provided")
    if t == "journal" and a == "create":
        entry = p.get("entry")
        if not isinstance(entry, str) or not entry.strip():
            raise RuntimeError("journal.create requires params.entry (non-empty string)")

    # Light validation for bulk operations on tasks
    if t == "todo" and a in {"update", "delete"}:
        scope = p.get("scope")
        if scope is not None and not isinstance(scope, str):
            raise RuntimeError("todo.update/delete params.scope must be a string if provided")
        if isinstance(scope, str) and scope.strip().lower() not in {"all", "pending", "completed"}:
            raise RuntimeError("todo.update/delete params.scope must be one of 'all', 'pending', 'completed'")
        if a == "update" and "scope" in p and "status" not in p:
            raise RuntimeError("todo.update bulk requires params.status when params.scope is provided")


def extract_actions(text: str) -> Dict[str, List[Dict[str, Any]]]:
    logger.info("extract_actions: planning actions for text: %s", text)
    system = (
        "You are a planner for a todo+journal assistant. Parse the user's message and "
        "respond ONLY with a STRICT JSON object with key 'actions'.\n\n"
        "Rules (MUST follow exactly):\n"
        "- Output JSON only (no prose).\n"
        "- actions is an array of objects with EXACT shape: {\"type\": string, \"action\": string, \"params\": object}.\n"
        "- Allowed type: 'todo', 'journal', or 'unknown'.\n"
        "- Allowed action: 'create' | 'read' | 'update' | 'delete'.\n\n"
        
        "**Type Classification Guidelines:**\n"
        "- **journal**: Use for emotional expressions, reflections, feelings, personal thoughts, or sentiment-based statements.\n"
        "  Examples: 'I felt really good today', 'Honestly, I've been struggling', 'Today was stressful', 'Feeling grateful', 'I think I handled it well'.\n"
        "- **todo**: Use for actionable tasks, commands, or requests with clear action verbs.\n"
        "  Examples: 'Add buy milk', 'Create task to review code', 'Mark task complete', 'List my tasks'.\n"
        "- **unknown**: Use ONLY for unrelated messages (greetings, questions about weather, random chat, etc.).\n\n"
        
        "- For todo.create: params MUST include {\"description\": string}. "
        "If a due date/time exists, include \"due\" (string like 'tomorrow', 'next Monday 9am'). "
        "If the user says 'remind me in X hours/days' or sets a specific reminder time, include \"reminder\" (string like 'in 2 hours', 'tomorrow 3pm'). "
        "Keep description concise and imperative (e.g., 'fix my headset').\n"
        "- For todo.read (list tasks): Extract optional filters if present in the message and place them under params using these exact keys: \n"
        "  {status: 'pending'|'completed', limit: number, dueBefore: string, dueAfter: string, tags: string[] or string, query: string}.\n"
        "  Only include filters that are explicitly implied by the message; omit unknowns.\n"
        "- For journal.create: params MUST include {\"entry\": string}. Capture the full emotional/reflective content.\n"
        "- For todo.update/delete of many: include params.scope with one of 'all', 'pending', or 'completed'. For bulk update also include params.status (e.g., 'completed').\n"
        "- For update/delete: prefer an explicit \"id\" when user provides it; otherwise include a discriminating field such as \"description\" (todo) or \"entry\" (journal).\n"
        "- For unknown type: set action to 'none' and leave params empty {}.\n"
        "- If the input asks for multiple things, return multiple actions in order.\n"
        "- Do not add extra keys beyond type, action, params; do not include comments."
    )
    user = f"Message: {text}\n\nReturn only the strict JSON described above."
    content = _groq_chat(
        [{"role": "system", "content": system}, {"role": "user", "content": user}],
        response_json=True,
        temperature=0.1,
        max_tokens=512,
    )

    # Log raw model content for debugging (should be JSON per response_format)
    try:
        logger.debug("extract_actions: raw model content: %s", content)
    except Exception:
        pass

    try:
        data = json.loads(content)
    except Exception as e:
        logger.exception("extract_actions: model returned invalid JSON: %s", e)
        raise RuntimeError("Invalid JSON returned by action planner") from e

    # Basic shape check
    if not isinstance(data, dict) or "actions" not in data:
        logger.error("extract_actions: missing 'actions' key in planner output")
        raise RuntimeError("Planner output missing required 'actions' key")

    actions = data["actions"]
    if not isinstance(actions, list):
        logger.error("extract_actions: 'actions' must be a list")
        raise RuntimeError("'actions' must be a list")

    # Validate each action strictly
    for idx, act in enumerate(actions):
        try:
            _validate_action_shape(act)
        except Exception as e:
            logger.exception("extract_actions: invalid action at index %d: %s", idx, e)
            raise RuntimeError(f"Invalid action at index {idx}: {e}") from e
    
    # Clean actions to ensure no extra fields
    cleaned_actions = []
    for act in actions:
        cleaned_actions.append({
            "type": act["type"],
            "action": act["action"],
            "params": act.get("params", {}),
        })

    logger.info("extract_actions: produced %d validated actions", len(cleaned_actions))
    return {"actions": cleaned_actions}


def generate_reminder_message(task_description: str, time_context: str) -> str:
    """
    Generate a casual, natural language reminder message for a task.
    
    Args:
        task_description: The task description
        time_context: Context like "due in 2 hours", "overdue by 1 day", "due now"
    
    Returns:
        A casual reminder message
    """
    prompt = f"""Generate a brief, casual reminder message for a task.

Task: {task_description}
Time: {time_context}

Requirements:
- Keep it simple and casual
- State the task and time info clearly
- No extra questions or suggestions
- 1-2 sentences max

Examples:
- "Hey! Your task 'Submit report' is due in 1 hour."
- "Reminder: 'Buy groceries' is due now."
- "Heads up - 'Call mom' was due 2 days ago."

Generate only the reminder message, nothing else."""

    try:
        messages = [
            {"role": "system", "content": "You are a helpful assistant that generates brief, casual task reminders."},
            {"role": "user", "content": prompt}
        ]
        
        response = _groq_chat(messages, temperature=0.7, max_tokens=100)
        
        # Clean up response
        message = response.strip()
        # Remove quotes if LLM wrapped it
        if message.startswith('"') and message.endswith('"'):
            message = message[1:-1]
        if message.startswith("'") and message.endswith("'"):
            message = message[1:-1]
        
        logger.info("Generated reminder message for task: %s", task_description[:50])
        return message
        
    except Exception as e:
        logger.error("Failed to generate reminder message: %s", e)
        # Fallback to simple template
        return f"Reminder: '{task_description}' - {time_context}"
