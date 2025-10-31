from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

class TaskOut(BaseModel):
    id: int = Field(..., description="Unique identifier for the task")
    user_id: str = Field(..., description="Unique identifier for the user")
    description: str = Field(..., description="The content of the task")
    status: str = Field(..., description="The current status of the task")
    created_at: datetime = Field(..., description="The creation timestamp of the task")
    due_date: Optional[datetime] = Field(None, description="The due date of the task")

    model_config = {
        "from_attributes": True
    }


class CompleteTaskResponse(BaseModel):
    status: str = Field(..., description="Status of the operation")
    task_id: int = Field(..., description="Unique identifier for the task")
    status_after: str = Field(..., description="Status of the task after completion")


class JournalOut(BaseModel):
    id: int = Field(..., description="Unique identifier for the journal entry")
    user_id: str = Field(..., description="Unique identifier for the user")
    entry: str = Field(..., description="The content of the journal entry")
    summary: Optional[str] = Field(None, description="Summary of the journal entry")
    sentiment: Optional[str] = Field(None, description="Sentiment analysis result")
    created_at: datetime = Field(..., description="The creation timestamp of the journal entry")

    model_config = {
        "from_attributes": True
    }
