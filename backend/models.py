import re
import uuid
from datetime import date, datetime, timezone
from typing import Literal

from blocked_usernames import PROFANE_USERNAMES
from pydantic import EmailStr, field_serializer, model_validator
from sqlalchemy import JSON, Column
from sqlmodel import Field, Relationship, SQLModel

ColumnId = Literal["backlog", "todo", "in_progress", "done"]


def _strip_blank_template_items(items: list[str]) -> list[str]:
    return [item.strip() for item in items if item.strip()]


class DailyTemplate(SQLModel):
    """Drafted through a popup styled like the real "Add task" dialog, but
    it never creates a task - Project/Column in that popup are display-only
    (a template always lands in `todo` under its own project once
    generated); only title/description/checklist are real. `title` is
    optional - the generated card is always named after the project and
    date; a title here is just appended to that, not a replacement for it.
    """

    title: str | None = None
    description: str | None = None
    checklist: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def clean(self) -> "DailyTemplate":
        self.title = (self.title or "").strip() or None
        self.description = (self.description or "").strip() or None
        self.checklist = _strip_blank_template_items(self.checklist)
        return self


_USERNAME_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9_-]{2,29}$")
_PASSWORD_SPECIAL_RE = re.compile(r"[^A-Za-z0-9\s]")


def _validate_username(value: str) -> str:
    value = value.strip()
    if not _USERNAME_RE.match(value):
        raise ValueError(
            "username must be 3-30 characters, start with a letter, "
            "and contain only letters, numbers, underscores, or hyphens"
        )
    if value.lower() in PROFANE_USERNAMES:
        raise ValueError("username contains a reserved or inappropriate word")
    return value


def _validate_password(value: str) -> str:
    if len(value) < 8:
        raise ValueError("password must be at least 8 characters")
    if not _PASSWORD_SPECIAL_RE.search(value):
        raise ValueError("password must contain at least one special character")
    return value


class User(SQLModel, table=True):
    __tablename__ = "users"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    email: EmailStr = Field(unique=True, index=True)
    username: str = Field(unique=True, index=True)
    hashed_password: str
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


class UserCreate(SQLModel):
    email: EmailStr
    username: str
    password: str

    @model_validator(mode="after")
    def validate(self) -> "UserCreate":
        self.username = _validate_username(self.username)
        self.password = _validate_password(self.password)
        return self


class UserLogin(SQLModel):
    email: EmailStr
    password: str


class UserPublic(SQLModel):
    id: uuid.UUID
    email: str
    username: str
    created_at: datetime


class AuthResponse(SQLModel):
    user: UserPublic
    token: str


class Project(SQLModel, table=True):
    """A time-tracking bucket tasks can optionally link to.

    Chart color is derived client-side from each project's position in the
    created_at-ordered list (see frontend/src/lib/project-palette.ts) -
    purely a display detail, so it isn't persisted here.
    """

    __tablename__ = "projects"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID = Field(foreign_key="users.id", ondelete="CASCADE", index=True)
    name: str
    description: str | None = None
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    daily_enabled: bool = Field(default=False)
    daily_template: DailyTemplate | None = Field(default=None, sa_column=Column(JSON))
    daily_last_generated: str | None = Field(default=None)
    tasks: list["Task"] = Relationship(
        back_populates="project",
        sa_relationship_kwargs={"foreign_keys": "[Task.project_id]"},
    )

    @field_serializer("daily_template")
    def serialize_daily_template(
        self, template: DailyTemplate | dict | None
    ) -> dict | None:
        # The JSON column returns a plain dict; model instances arrive when the
        # field is constructed from a Pydantic payload. Normalize to dicts so
        # response serialization never warns about an unexpected type.
        if template is None:
            return None
        if isinstance(template, DailyTemplate):
            return template.model_dump()
        return template


class ProjectCreate(SQLModel):
    name: str
    description: str | None = None
    daily_enabled: bool = False
    daily_template: DailyTemplate | None = None

    @model_validator(mode="after")
    def validate_daily(self) -> "ProjectCreate":
        if self.daily_enabled and self.daily_template is None:
            raise ValueError("daily_enabled requires a daily_template")
        return self


class ProjectUpdate(SQLModel):
    name: str
    description: str | None = None
    daily_enabled: bool = False
    daily_template: DailyTemplate | None = None

    @model_validator(mode="after")
    def validate_daily(self) -> "ProjectUpdate":
        if self.daily_enabled and self.daily_template is None:
            raise ValueError("daily_enabled requires a daily_template")
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
    user_id: uuid.UUID = Field(foreign_key="users.id", ondelete="CASCADE", index=True)
    title: str
    description: str | None = None
    column_id: str = Field(index=True)
    # Deleting the project unlinks the task (falls back to "Not defined");
    # it never deletes or blocks deletion of the task.
    project_id: uuid.UUID | None = Field(
        default=None, foreign_key="projects.id", ondelete="SET NULL", index=True
    )
    project: Project | None = Relationship(
        back_populates="tasks",
        sa_relationship_kwargs={"foreign_keys": "[Task.project_id]"},
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

    @field_serializer("checklist")
    def serialize_checklist(
        self, checklist: list[ChecklistItem] | list[dict]
    ) -> list[dict]:
        # The JSON column returns plain dicts; model instances arrive when the
        # field is constructed from a Pydantic payload. Normalize to dicts so
        # response serialization never warns about an unexpected type.
        return [
            item.model_dump() if isinstance(item, ChecklistItem) else item
            for item in checklist
        ]


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
