
import logging
from fastapi import HTTPException
from typing import List, Tuple
from app import crud
from app.utils import llm

logger = logging.getLogger("services")



def process_telex_message(user_id: str, message: str) -> dict:
    """Classify message and perform the corresponding action using Groq."""
    logger.info(f"Processing telex message for user_id={user_id}")
    intent = llm.classify_intent(message)
    logger.info(f"Intent classified as '{intent}' for user_id={user_id}")
    if intent == "todo":
        try:
            action = llm.extract_todo_action(message)
            task = crud.create_task(user_id, action)
            logger.info(f"Task created for user_id={user_id}, task_id={task.id}")
            return {"status": "ok", "message": f'Added "{task.description}" to your todo list.', "task_id": task.id}
        except Exception as e:
            logger.error(f"Failed to create task for user_id={user_id}: {e}")
            raise HTTPException(status_code=500, detail="Failed to create task")

    if intent == "journal":
        try:
            sentiment, summary = llm.analyze_entry(message)
            journal = crud.create_journal(user_id, message, summary, sentiment)
            logger.info(f"Journal entry created for user_id={user_id}, journal_id={journal.id}")
            return {
                "status": "ok",
                "message": "Journal saved.",
                "summary": summary,
                "sentiment": sentiment,
                "journal_id": journal.id,
            }
        except Exception as e:
            logger.error(f"Failed to create journal entry for user_id={user_id}: {e}")
            raise HTTPException(status_code=500, detail="Failed to create journal entry")

    logger.warning(f"Could not determine intent for user_id={user_id}")
    raise HTTPException(status_code=400, detail="Could not determine intent (todo or journal).")



def list_tasks(user_id: str):
    logger.info(f"Listing tasks for user_id={user_id}")
    try:
        tasks = crud.get_tasks(user_id)
        logger.info(f"Fetched {len(tasks)} tasks for user_id={user_id}")
        return tasks
    except Exception as e:
        logger.error(f"Failed to list tasks for user_id={user_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to list tasks")



def complete_task(task_id: int) -> dict:
    logger.info(f"Completing task id={task_id}")
    try:
        t = crud.complete_task(task_id)
        if not t:
            logger.warning(f"Task id={task_id} not found for completion.")
            raise HTTPException(status_code=404, detail="Task not found")
        logger.info(f"Task id={task_id} marked as completed.")
        return {"status": "ok", "task_id": t.id, "status_after": t.status}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to complete task id={task_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to complete task")



def list_journals(user_id: str, limit: int = 20):
    logger.info(f"Listing journals for user_id={user_id}, limit={limit}")
    try:
        journals = crud.get_journals(user_id, limit)
        logger.info(f"Fetched {len(journals)} journals for user_id={user_id}")
        return journals
    except Exception as e:
        logger.error(f"Failed to list journals for user_id={user_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to list journals")
