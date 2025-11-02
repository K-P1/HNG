from __future__ import annotations

from sqlalchemy import Integer, String, Text, DateTime
from sqlalchemy.orm import declarative_base
from datetime import datetime, timezone
from sqlalchemy.orm import Mapped, mapped_column

Base = declarative_base()


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[str] = mapped_column(String(255), index=True)
    description: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(50), default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    due_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)


class Journal(Base):
    __tablename__ = "journals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[str] = mapped_column(String(255), index=True)
    entry: Mapped[str] = mapped_column(Text)
    summary: Mapped[str] = mapped_column(Text, nullable=True)
    sentiment: Mapped[str] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

