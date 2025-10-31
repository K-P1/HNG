from fastapi import HTTPException
from typing import List, Tuple
from app import crud
from app.utils import llm


def process_telex_message(user_id: str, message: str) -> dict:
    """Classify message and perform the corresponding action using Groq."""
    intent = llm.classify_intent(message)
    if intent == "todo":
        action = llm.extract_todo_action(message)
        task = crud.create_task(user_id, action)
        return {"status": "ok", "message": f'Added "{task.description}" to your todo list.', "task_id": task.id}

    if intent == "journal":
        sentiment, summary = llm.analyze_entry(message)
        journal = crud.create_journal(user_id, message, summary, sentiment)
        return {
            "status": "ok",
            "message": "Journal saved.",
            "summary": summary,
            "sentiment": sentiment,
            "journal_id": journal.id,
        }

    raise HTTPException(status_code=400, detail="Could not determine intent (todo or journal).")


def list_tasks(user_id: str):
    return crud.get_tasks(user_id)


def complete_task(task_id: int) -> dict:
    t = crud.complete_task(task_id)
    if not t:
        raise HTTPException(status_code=404, detail="Task not found")
    return {"status": "ok", "task_id": t.id, "status_after": t.status}


def list_journals(user_id: str, limit: int = 20):
    return crud.get_journals(user_id, limit)
