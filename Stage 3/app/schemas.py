from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from enum import Enum


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------
class TaskStatus(str, Enum):
    pending = "pending"
    completed = "completed"
    cancelled = "cancelled"


# ---------------------------------------------------------------------------
# Task Schemas
# ---------------------------------------------------------------------------
class TaskCreate(BaseModel):
    description: str = Field(..., description="Description or title of the task")
    due_date: Optional[datetime] = Field(None, description="Optional due date of the task")


class TaskUpdate(BaseModel):
    description: Optional[str] = Field(None, description="Updated description of the task")
    status: Optional[TaskStatus] = Field(None, description="New status of the task")
    due_date: Optional[datetime] = Field(None, description="Updated due date")


class TaskOut(BaseModel):
    id: int = Field(..., description="Unique identifier for the task")
    user_id: str = Field(..., description="Unique identifier for the user who owns this task")
    description: str = Field(..., description="The content of the task")
    status: TaskStatus = Field(..., description="The current status of the task")
    created_at: datetime = Field(..., description="Timestamp when the task was created")
    due_date: Optional[datetime] = Field(None, description="The due date of the task")

    model_config = {"from_attributes": True}


class TaskList(BaseModel):
    count: int = Field(..., description="Total number of tasks returned")
    tasks: List[TaskOut] = Field(..., description="List of tasks")


class CompleteTaskResponse(BaseModel):
    status: str = Field(..., description="Status of the operation (e.g., 'success')")
    task_id: int = Field(..., description="ID of the task updated")
    status_after: TaskStatus = Field(..., description="Status of the task after completion")


# ---------------------------------------------------------------------------
# Journal Schemas
# ---------------------------------------------------------------------------
class JournalCreate(BaseModel):
    entry: str = Field(..., description="Full text of the journal entry")
    summary: Optional[str] = Field(None, description="Optional summary of the entry")
    sentiment: Optional[str] = Field(None, description="Sentiment label (positive, neutral, or negative)")


class JournalUpdate(BaseModel):
    entry: Optional[str] = Field(None, description="Updated journal text")
    summary: Optional[str] = Field(None, description="Updated summary")
    sentiment: Optional[str] = Field(None, description="Updated sentiment label")


class JournalOut(BaseModel):
    id: int = Field(..., description="Unique identifier for the journal entry")
    user_id: str = Field(..., description="Unique identifier for the user who owns this journal entry")
    entry: str = Field(..., description="Full content of the journal entry")
    summary: Optional[str] = Field(None, description="Auto-generated summary of the journal entry")
    sentiment: Optional[str] = Field(None, description="Sentiment result ('positive', 'neutral', or 'negative')")
    created_at: datetime = Field(..., description="Timestamp when the journal entry was created")

    model_config = {"from_attributes": True}


class JournalList(BaseModel):
    count: int = Field(..., description="Total number of journal entries returned")
    journals: List[JournalOut] = Field(..., description="List of journal entries")
