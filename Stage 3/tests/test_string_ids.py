import os
import sys
import pytest

# Ensure project root is importable
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import crud
from app.services import llm_service


@pytest.mark.asyncio
async def test_todo_update_accepts_string_id():
    # Create a task
    t = await crud.create_task("u_strid", "Mark me pending")

    # Execute an update action with id as a string
    actions = [
        {"type": "todo", "action": "update", "params": {"id": str(t.id), "status": "pending"}},
    ]
    res = await llm_service.execute_actions("u_strid", actions, "update by string id")

    assert res["status"] == "ok"
    assert f"Updated task #{t.id}" in res["message"]


@pytest.mark.asyncio
async def test_todo_update_rejects_bad_id():
    # Try to update with a non-numeric id
    actions = [
        {"type": "todo", "action": "update", "params": {"id": "abc", "status": "completed"}},
    ]
    res = await llm_service.execute_actions("u_strid2", actions, "bad id")

    # Should not raise, but report an error and not crash the whole batch
    assert res["status"] == "ok"
    assert "Couldn't update task: invalid id" in res["message"]
