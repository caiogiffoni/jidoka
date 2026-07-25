import uuid
from datetime import date, datetime, timezone
from typing import Literal

from pydantic import model_validator
from sqlalchemy import JSON, Column
from sqlmodel import Field, SQLModel

ColumnId = Literal["backlog", "todo", "in_progress", "done"]


class Project(SQLModel, table=True):
    """A time-tracking bucket tasks can optionally link to.

    Chart color is derived client-side from each project's position in the
    created_at-ordered list (see frontend/src/lib/project-palette.ts) -
    purely a display detail, so it isn't persisted here.
    """

    __tablename__ = "projects"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    name: str
    description: str | None = None
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    daily_enabled: bool = Field(default=False)
    daily_template: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    daily_last_generated: str | None = Field(default=None)


def _strip_blank_template_items(items: list[str]) -> list[str]:
    return [item.strip() for item in items if item.strip()]


class ProjectCreate(SQLModel):
    name: str
    description: str | None = None
    daily_enabled: bool = False
    daily_template: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def strip_blank_template_items(self) -> "ProjectCreate":
        self.daily_template = _strip_blank_template_items(self.daily_template)
        return self


class ProjectUpdate(SQLModel):
    name: str
    description: str | None = None
    daily_enabled: bool = False
    daily_template: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def strip_blank_template_items(self) -> "ProjectUpdate":
        self.daily_template = _strip_blank_template_items(self.daily_template)
        return self


class DailyProjectStat(SQLModel):
    """One flat row of GET /work-blocks/stats/daily's response grid."""

    date: str  # "YYYY-MM-DD", UTC calendar day
    project_id: uuid.UUID | None
    project_name: str | None
    minutes: float


class ChecklistItem(SQLModel):
    text: str
    checked: bool = False


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
    archived: bool = Field(default=False, index=True)
    checklist: list[ChecklistItem] = Field(
        default_factory=list, sa_column=Column(JSON)
    )
    due_date: date | None = None
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


def _strip_blank_checklist_items(items: list[ChecklistItem]) -> list[ChecklistItem]:
    cleaned = []
    for item in items:
        text = item.text.strip()
        if text:
            cleaned.append(ChecklistItem(text=text, checked=item.checked))
    return cleaned


class TaskCreate(SQLModel):
    title: str
    description: str | None = None
    column_id: ColumnId = "todo"
    project_id: uuid.UUID | None = None
    checklist: list[ChecklistItem] = Field(default_factory=list)

    @model_validator(mode="after")
    def strip_blank_checklist_items(self) -> "TaskCreate":
        self.checklist = _strip_blank_checklist_items(self.checklist)
        return self


class TaskUpdate(SQLModel):
    title: str
    description: str | None = None
    project_id: uuid.UUID | None = None
    checklist: list[ChecklistItem] = Field(default_factory=list)
    due_date: date | None = None

    @model_validator(mode="after")
    def strip_blank_checklist_items(self) -> "TaskUpdate":
        self.checklist = _strip_blank_checklist_items(self.checklist)
        return self


class TaskMove(SQLModel):
    column_id: ColumnId
    position: int = Field(ge=0)


class TaskArchive(SQLModel):
    archived: bool


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
