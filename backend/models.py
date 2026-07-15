import uuid
from datetime import datetime, timezone
from typing import Literal

from pydantic import model_validator
from sqlmodel import Field, SQLModel

ColumnId = Literal["todo", "in_progress", "done"]


class Project(SQLModel, table=True):
    """A time-tracking bucket tasks can optionally link to.

    color_slot is assigned once, from a Postgres sequence, at creation and
    never recomputed - the dashboard chart maps color_slot % palette_length
    to a fixed hue, so deleting or filtering projects must never repaint
    the survivors' colors.
    """

    __tablename__ = "projects"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    name: str
    color_slot: int
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


class ProjectCreate(SQLModel):
    name: str


class DailyProjectStat(SQLModel):
    """One flat row of GET /work-blocks/stats/daily's response grid."""

    date: str  # "YYYY-MM-DD", UTC calendar day
    project_id: uuid.UUID | None
    project_name: str | None
    minutes: float


class Task(SQLModel, table=True):
    __tablename__ = "tasks"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    title: str
    description: str | None = None
    column_id: str = Field(index=True)
    # Deleting the project unlinks the task (falls back to "Not defined");
    # it never deletes or blocks deletion of the task.
    project_id: uuid.UUID | None = Field(
        default=None, foreign_key="projects.id", ondelete="SET NULL", index=True
    )
    # Display order within a column; the frontend renders tasks sorted by it.
    position: int
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


class TaskCreate(SQLModel):
    title: str
    description: str | None = None
    column_id: ColumnId = "todo"
    project_id: uuid.UUID | None = None


class TaskMove(SQLModel):
    column_id: ColumnId
    position: int = Field(ge=0)


class WorkBlock(SQLModel, table=True):
    """One completed pomodoro or manually logged stretch of work on a task.

    Append-only rows, not a mutating counter, so history is kept. Timer
    blocks carry timestamps; manual entries carry only minutes. Stopped
    (aborted) focus sessions are never persisted here.
    """

    __tablename__ = "work_blocks"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    task_id: uuid.UUID = Field(foreign_key="tasks.id", ondelete="CASCADE", index=True)
    started_at: datetime | None = None
    ended_at: datetime | None = None
    minutes: int | None = None
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


class WorkBlockCreate(SQLModel):
    started_at: datetime | None = None
    ended_at: datetime | None = None
    minutes: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def check_timed_or_manual(self) -> "WorkBlockCreate":
        timed = self.started_at is not None and self.ended_at is not None
        if not timed and self.minutes is None:
            raise ValueError("provide started_at + ended_at, or minutes")
        if timed and self.ended_at < self.started_at:
            raise ValueError("ended_at must not be before started_at")
        return self
