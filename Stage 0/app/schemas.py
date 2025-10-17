from datetime import datetime, timezone
from pydantic import BaseModel, Field, EmailStr


class UserModel(BaseModel):
    email: EmailStr
    name: str
    stack: str


class ResponseModel(BaseModel):
    status: str = Field(default="success")
    user: UserModel
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"))
    fact: str = Field(default="No cat fact available right now.")
