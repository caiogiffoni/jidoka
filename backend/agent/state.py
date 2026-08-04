"""Agent state and change schemas for the HITL board agent."""

import uuid
from typing import Annotated, Literal, TypedDict

from langchain_core.messages import AnyMessage
from pydantic import BaseModel
from sqlmodel import Field, SQLModel

from models import ChecklistItem, ColumnId


class CreateTaskChange(SQLModel):
    type: Literal["create_task"] = "create_task"
    title: str
    description: str | None = None
    column_id: ColumnId = "todo"
    project_id: uuid.UUID | None = None
    checklist: list[ChecklistItem] = Field(default_factory=list)


class ProposedDiff(BaseModel):
    changes: list[CreateTaskChange]


class AppliedResult(BaseModel):
    created_tasks: list[dict]


class AgentState(TypedDict):
    messages: Annotated[list[AnyMessage], lambda a, b: a + b]
    proposed_changes: list[CreateTaskChange]
    approved: bool | None
    applied_results: list[dict]
