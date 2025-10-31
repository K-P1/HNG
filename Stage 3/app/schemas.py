from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class TelexMessage(BaseModel):
    user_id: str
    message: str


class TaskCreate(BaseModel):
    user_id: str
    description: str
    due_date: Optional[datetime] = None


class TaskOut(BaseModel):
    id: int
    user_id: str
    description: str
    status: str
    created_at: datetime
    due_date: Optional[datetime] = None

    model_config = {
        "from_attributes": True
    }


class TelexResponse(BaseModel):
    status: str
    message: str
    task_id: Optional[int] = None
    journal_id: Optional[int] = None
    summary: Optional[str] = None
    sentiment: Optional[str] = None


class CompleteTaskResponse(BaseModel):
    status: str
    task_id: int
    status_after: str


class JournalCreate(BaseModel):
    user_id: str
    entry: str


class JournalOut(BaseModel):
    id: int
    user_id: str
    entry: str
    summary: Optional[str] = None
    sentiment: Optional[str] = None
    created_at: datetime

    model_config = {
        "from_attributes": True
    }
