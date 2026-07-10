import uuid
from datetime import datetime, timezone
from typing import Literal

from sqlmodel import Field, SQLModel

ColumnId = Literal["todo", "in_progress", "done"]


class Task(SQLModel, table=True):
    __tablename__ = "tasks"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    title: str
    description: str | None = None
    column_id: str = Field(index=True)
    # Display order within a column; the frontend renders tasks sorted by it.
    position: int
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


class TaskCreate(SQLModel):
    title: str
    description: str | None = None
    column_id: ColumnId = "todo"
