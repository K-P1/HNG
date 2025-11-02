import pytest

from app.services import llm_service


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "resource,update_params,delete_params,user_id",
    [
        (
            "todo",
            {"description": "nonexistent task", "status": "completed"},
            {"description": "nonexistent task"},
            "u_soft_todo",
        ),
        (
            "journal",
            {"entry": "text that will not match"},
            {"entry": "text that will not match"},
            "u_soft_journal",
        ),
    ],
)
async def test_update_delete_not_found_are_soft(resource, update_params, delete_params, user_id):
    actions = [
        {"type": resource, "action": "update", "params": update_params},
        {"type": resource, "action": "delete", "params": delete_params},
    ]

    res = await llm_service.execute_actions(user_id, actions, f"try missing {resource}")
    assert res["status"] == "ok"
    msg = res.get("message", "")
    # Accept any of the soft-not-found phrasing
    assert ("Couldn't find" in msg) or ("wasn't found" in msg)
    # errors metadata should exist
    errors = res.get("errors", [])
    assert isinstance(errors, list) and errors, "Expected errors metadata for soft failures"
