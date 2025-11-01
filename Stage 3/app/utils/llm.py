
import logging
from typing import Tuple, Dict, Any, List
import os
import json

logger = logging.getLogger("llm")



def _require_env():
    if os.getenv("LLM_PROVIDER", "").lower() != "groq":
        logger.error("LLM_PROVIDER must be 'groq'")
        raise RuntimeError("LLM_PROVIDER must be 'groq'")
    if not os.getenv("GROQ_API_KEY"):
        logger.error("GROQ_API_KEY is not configured")
        raise RuntimeError("GROQ_API_KEY is not configured")



def _get_groq_client():
    from groq import Groq  # type: ignore
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        logger.error("GROQ_API_KEY is not configured")
        raise RuntimeError("GROQ_API_KEY is not configured")
    logger.info("Groq client initialized.")
    return Groq(api_key=api_key)



def _groq_chat(messages: list[dict[str, str]], *, response_json: bool = False, temperature: float = 0.2, max_tokens: int = 256) -> str:
    _require_env()
    client = _get_groq_client()
    model = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
    kwargs: Dict[str, Any] = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if response_json:
        kwargs["response_format"] = {"type": "json_object"}

    logger.info(f"Sending chat completion to Groq: model={model}, messages={messages}")
    resp = client.chat.completions.create(**kwargs)
    if not resp or not getattr(resp, "choices", None):
        logger.error("Groq returned no choices")
        raise RuntimeError("Groq returned no choices")
    content = resp.choices[0].message.content
    if not content:
        logger.error("Groq returned empty content")
        raise RuntimeError("Groq returned empty content")
    logger.info("Groq chat completion successful.")
    return content


def classify_intent(text: str) -> str:
    """Classify text as 'todo', 'journal', or 'unknown'. Fails fast on errors."""
    logger.info(f"Classifying intent for text: {text}")
    system = (
        "You are an intent classifier for a personal assistant."
        " Decide if the user's message is a TODO (actionable task),"
        " a JOURNAL (a reflective entry or feeling), or UNKNOWN."
        " Respond ONLY as a compact JSON object with key 'intent'"
        " whose value is one of: 'todo', 'journal', 'unknown'."
    )
    user = f"Message: {text}"
    try:
        content = _groq_chat([
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ], response_json=True, temperature=0.0, max_tokens=40)
        data = json.loads(content)
        intent = str(data.get("intent", "unknown")).lower()
        if intent not in {"todo", "journal", "unknown"}:
            logger.warning(f"Intent classified as unknown for text: {text}")
            return "unknown"
        logger.info(f"Intent classified as '{intent}' for text: {text}")
        return intent
    except Exception as e:
        logger.error(f"Failed to classify intent for text: {text}: {e}")
        return "unknown"
        raise RuntimeError("Invalid intent from Groq")
    return intent


def extract_todo_action(text: str) -> str:
    """Extract a concise action phrase for a TODO. Fails fast on errors."""
    system = (
        "Extract a concise actionable TODO phrase from the user's message."
        " Return ONLY JSON: {\"action\": \"...\"}."
    )
    user = f"Message: {text}"
    content = _groq_chat([
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ], response_json=True, temperature=0.2, max_tokens=60)

    data = json.loads(content)
    action = str(data.get("action", "")).strip()
    if not action:
        raise RuntimeError("Groq did not return an action")
    return action


def analyze_entry(text: str) -> Tuple[str, str]:
    """Return (sentiment, summary). Fails fast on errors.

    Sentiment: 'positive' | 'neutral' | 'negative'
    Summary: a short 1–2 sentence summary
    """
    system = (
        "You analyze journal entries."
        " Return a short summary (<= 2 sentences) and a sentiment label"
        " from {positive, neutral, negative}."
        " Respond ONLY as JSON: {\"summary\": \"...\", \"sentiment\": \"...\"}."
    )
    user = f"Entry: {text}"
    content = _groq_chat([
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ], response_json=True, temperature=0.2, max_tokens=120)

    data = json.loads(content)
    summary = str(data.get("summary", "")).strip()
    sentiment = str(data.get("sentiment", "")).lower()
    if not summary:
        raise RuntimeError("Groq did not return a summary")
    if sentiment not in {"positive", "neutral", "negative"}:
        raise RuntimeError("Groq returned invalid sentiment")
    return sentiment, summary


def plan_actions(message: str) -> Dict[str, Any]:
    """Return a structured plan of actions for the assistant to execute.

    The model must return strict JSON with this shape:
    {
      "actions": [
        {
          "type": "create_task" | "list_tasks" | "update_task" | "delete_task" |
                   "create_journal" | "list_journals" | "update_journal" | "delete_journal",
          "params": { ... }
        }, ...
      ]
    }

    Allowed params per type (selectors can be by id OR by text when id is unknown):
    - create_task: {"description": str, "due_date": str|null}
    - list_tasks: {"user_id": str|null}
    - update_task: {"id": int|null, "description": str|null, "status": "pending|completed"|null, "due_date": str|null, "query": str|null, "title": str|null}
    - delete_task: {"id": int|null, "description": str|null, "query": str|null, "title": str|null}
    - create_journal: {"entry": str}
    - list_journals: {"user_id": str|null, "limit": int|null}
    - update_journal: {"id": int|null, "entry": str|null, "summary": str|null, "sentiment": "positive|neutral|negative"|null, "query": str|null}
    - delete_journal: {"id": int|null, "entry": str|null, "summary": str|null, "query": str|null}
    """
    logger.info("Planning actions via Groq for message: %s", message)
    system = (
        "You are a controller for a todo+journal assistant. Parse the user's message and output a STRICT JSON object "
        "with an 'actions' array describing the operations to perform. Support multiple actions in order. "
        "When the user does not provide an id for update/delete, include a text selector (e.g., description/query/title/entry) so the backend can resolve the item. "
        "Only output JSON, no extra text. Use the provided schema and be conservative with IDs if not specified."
    )
    user = f"Message: {message}\n\nReturn only JSON with an 'actions' array per the schema."

    content = _groq_chat([
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ], response_json=True, temperature=0.1, max_tokens=400)

    try:
        data = json.loads(content)
    except Exception as e:
        logger.error("Groq returned invalid JSON for plan_actions: %s", e)
        raise

    # Normalize minimal structure
    actions = data.get("actions")
    # Also accept nested shape { "plan": { "actions": [...] } }
    if actions is None and isinstance(data.get("plan"), dict):
        actions = data["plan"].get("actions")

    # Log the raw plan (truncated) to diagnose empty-actions fallbacks
    try:
        preview = json.dumps(data)
        if len(preview) > 500:
            preview = preview[:500] + "..."
        logger.debug("plan_actions raw JSON preview: %s", preview)
    except Exception:
        pass

    if not isinstance(actions, list):
        logger.warning("plan_actions: missing or invalid 'actions'; returning empty plan")
        return {"actions": []}
    # Basic sanitization and normalization
    cleaned: List[Dict[str, Any]] = []

    type_map = {
        # tasks
        "add_task": "create_task",
        "create_todo": "create_task",
        "add_todo": "create_task",
        "show_tasks": "list_tasks",
        "list_todos": "list_tasks",
        "get_tasks": "list_tasks",
        "complete_task": "update_task",
        "update_task_status": "update_task",
        "remove_task": "delete_task",
        "delete_todo": "delete_task",
        # journals
        "add_journal": "create_journal",
        "create_note": "create_journal",
        "show_journals": "list_journals",
        "list_notes": "list_journals",
        "update_note": "update_journal",
        "remove_note": "delete_journal",
    }

    for a in actions:
        if not isinstance(a, dict):
            continue
        # Some planners use {action: verb, type: subject} pairs instead of our {type: operation}
        raw_type = str(a.get("type", "")).lower().strip()
        verb = str(a.get("action", "") or a.get("verb", "")).lower().strip()
        subject = str(a.get("subject", "") or a.get("entity", "") or a.get("target", "") or a.get("collection", "")).lower().strip() or raw_type

        # Start with raw type, then normalize; will be overridden by (verb,subject) mapping if present
        t = type_map.get(subject or str(a.get("type", "")).strip(), str(a.get("type", "")).strip())

        p = a.get("params") or {}
        if not isinstance(p, dict):
            p = {}

        # If planner provided flat parameters alongside action/type pair, merge them into params
        if not p:
            # Copy non-control keys as params
            p = {k: v for k, v in a.items() if k not in {"action", "type", "params"}}

        # Some planners nest arguments under an 'item' field. Flatten it into params.
        item = a.get("item")
        if isinstance(item, dict):
            for k, v in item.items():
                # Do not overwrite explicit params
                if k not in p:
                    p[k] = v
            # Infer subject from item.kind/type if present
            try:
                ik = str(item.get("kind") or item.get("type") or "").lower().strip()
                if ik and ik not in {"create", "list", "update", "delete", "remove", "add", "get", "show"}:
                    subject = subject or ik
            except Exception:
                pass

        # Merge optional selector object into params for id-less targeting
        sel = a.get("selector")
        if isinstance(sel, dict):
            for k, v in sel.items():
                # Do not overwrite explicit params
                if k not in p:
                    p[k] = v

        # Normalize common (verb,subject) pairs to our operation types
        op_from_pair = None
        if verb and subject:
            if subject in {"task", "todo", "todos"}:
                if verb in {"add", "create"}:
                    op_from_pair = "create_task"
                elif verb in {"list", "show", "get"}:
                    op_from_pair = "list_tasks"
                elif verb in {"update", "complete", "set"}:
                    op_from_pair = "update_task"
                elif verb in {"delete", "remove"}:
                    op_from_pair = "delete_task"
            elif subject in {"tasks"}:
                if verb in {"list", "show", "get"}:
                    op_from_pair = "list_tasks"
            elif subject in {"journal", "note"}:
                if verb in {"add", "create"}:
                    op_from_pair = "create_journal"
                elif verb in {"update", "set"}:
                    op_from_pair = "update_journal"
                elif verb in {"delete", "remove"}:
                    op_from_pair = "delete_journal"
            elif subject in {"journals", "notes"}:
                if verb in {"list", "show", "get"}:
                    op_from_pair = "list_journals"

        # If 'type' was actually a verb like 'create'/'list', promote it to verb when verb was empty
        if not verb and raw_type in {"create", "add", "list", "show", "get", "update", "complete", "set", "delete", "remove"}:
            verb = raw_type

        # Try to infer operation from (verb, subject) or from params when subject is ambiguous
        if op_from_pair:
            t = op_from_pair
        else:
            # Fallback: the 'type' field may already be an operation string
            t = type_map.get(str(a.get("type", "")).strip(), str(a.get("type", "")).strip())

        # If still not in our allowed set, infer from verb + params
        def infer_domain(params: Dict[str, Any], subj: str) -> str:
            s = (subj or "").lower().strip()
            if s in {"journal", "journals", "note", "notes"}:
                return "journal"
            # look at params
            keys = {k.lower() for k in params.keys()}
            if {"entry", "summary", "sentiment"} & keys:
                return "journal"
            return "task"

        allowed = {
            "create_task", "list_tasks", "update_task", "delete_task",
            "create_journal", "list_journals", "update_journal", "delete_journal",
        }

        if t not in allowed and verb:
            domain = infer_domain(p, subject)
            if verb in {"create", "add"}:
                t = "create_journal" if domain == "journal" else "create_task"
            elif verb in {"list", "show", "get"}:
                if domain == "journal":
                    t = "list_journals"
                else:
                    t = "list_tasks"
            elif verb in {"update", "set", "complete"}:
                t = "update_journal" if domain == "journal" else "update_task"
                # Map 'complete' to completed status if not provided
                if verb == "complete" and t == "update_task" and "status" not in p:
                    p["status"] = "completed"
            elif verb in {"delete", "remove"}:
                t = "delete_journal" if domain == "journal" else "delete_task"

        # Param normalizations
        if t == "create_task":
            # Allow title as alias for description
            if "description" not in p and isinstance(p.get("title"), str):
                p["description"] = p.get("title")
            # Combine due_date and due_time into a single due_date string the executor can parse
            # Accept 'due' or ('due_date' + 'due_time')
            if isinstance(p.get("due"), str) and not isinstance(p.get("due_date"), str):
                p["due_date"] = p.get("due")
            dd_val = p.get("due_date")
            dt_val = p.get("due_time")
            if isinstance(dd_val, str) and isinstance(dt_val, str):
                dd = dd_val.strip()
                dt = dt_val.strip()
                if dd and dt:
                    p["due_date"] = f"{dd} {dt}".strip()
        elif t in {"update_task", "delete_task"}:
            if "description" not in p and "query" not in p and isinstance(p.get("title"), str):
                p["description"] = p.get("title")
            # Map boolean completed -> status for update
            if t == "update_task" and "completed" in p and "status" not in p:
                try:
                    if bool(p.get("completed")):
                        p["status"] = "completed"
                except Exception:
                    pass
        elif t == "update_journal":
            sent = p.get("sentiment")
            if isinstance(sent, dict) and "label" in sent:
                p["sentiment"] = sent.get("label")

        if t in allowed and isinstance(p, dict):
            cleaned.append({"type": t, "params": p})
    logger.debug("plan_actions cleaned actions count: %d", len(cleaned))
    return {"actions": cleaned}
