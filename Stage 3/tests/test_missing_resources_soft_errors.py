import os
import sys
import pytest

# Ensure project root is importable
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.services import llm_service


@pytest.mark.asyncio
async def test_todo_update_delete_not_found_are_soft():
    actions = [
        {"type": "todo", "action": "update", "params": {"description": "nonexistent task", "status": "completed"}},
        {"type": "todo", "action": "delete", "params": {"description": "nonexistent task"}},
    ]

    res = await llm_service.execute_actions("u_soft", actions, "try operations on missing tasks")
    assert res["status"] == "ok"
    msg = res.get("message", "")
    assert "Couldn't find a task matching" in msg or "wasn't found" in msg
    # errors metadata should exist
    errors = res.get("errors", [])
    assert isinstance(errors, list) and errors, "Expected errors metadata for soft failures"


@pytest.mark.asyncio
async def test_journal_update_delete_not_found_are_soft():
    actions = [
        {"type": "journal", "action": "update", "params": {"entry": "text that will not match"}},
        {"type": "journal", "action": "delete", "params": {"entry": "text that will not match"}},
    ]

    res = await llm_service.execute_actions("u_soft_j", actions, "try operations on missing journals")
    assert res["status"] == "ok"
    msg = res.get("message", "")
    assert "Couldn't find a journal" in msg or "wasn't found" in msg
    errors = res.get("errors", [])
    assert isinstance(errors, list) and errors, "Expected errors metadata for soft failures"
