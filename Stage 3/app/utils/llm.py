from typing import Tuple, Dict, Any
import os
import json


def _require_env():
    if os.getenv("LLM_PROVIDER", "").lower() != "groq":
        raise RuntimeError("LLM_PROVIDER must be 'groq'")
    if not os.getenv("GROQ_API_KEY"):
        raise RuntimeError("GROQ_API_KEY is not configured")


def _get_groq_client():
    from groq import Groq  # type: ignore
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError("GROQ_API_KEY is not configured")
    return Groq(api_key=api_key)


def _groq_chat(messages: list[dict[str, str]], *, response_json: bool = False, temperature: float = 0.2, max_tokens: int = 256) -> str:
    _require_env()
    client = _get_groq_client()
    model = os.getenv("GROQ_MODEL", "llama-3.1-70b-versatile")
    kwargs: Dict[str, Any] = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if response_json:
        kwargs["response_format"] = {"type": "json_object"}

    resp = client.chat.completions.create(**kwargs)
    if not resp or not getattr(resp, "choices", None):
        raise RuntimeError("Groq returned no choices")
    content = resp.choices[0].message.content
    if not content:
        raise RuntimeError("Groq returned empty content")
    return content


def classify_intent(text: str) -> str:
    """Classify text as 'todo', 'journal', or 'unknown'. Fails fast on errors."""
    system = (
        "You are an intent classifier for a personal assistant."
        " Decide if the user's message is a TODO (actionable task),"
        " a JOURNAL (a reflective entry or feeling), or UNKNOWN."
        " Respond ONLY as a compact JSON object with key 'intent'"
        " whose value is one of: 'todo', 'journal', 'unknown'."
    )
    user = f"Message: {text}"
    content = _groq_chat([
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ], response_json=True, temperature=0.0, max_tokens=40)

    data = json.loads(content)
    intent = str(data.get("intent", "unknown")).lower()
    if intent not in {"todo", "journal", "unknown"}:
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
