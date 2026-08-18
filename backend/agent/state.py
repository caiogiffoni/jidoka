"""State schemas and change types for the HITL agent graph.

These objects are the contract between the agent's nodes, the SSE endpoint,
and the frontend diff approval UI.
"""

import uuid
from datetime import date
from typing import Annotated, Literal, TypedDict, Union

from langgraph.graph.message import add_messages
from pydantic import model_validator
from sqlmodel import Field, SQLModel

from models import ChecklistItem, Task, _strip_blank_checklist_items


class CreateTaskChange(SQLModel):
    """A single proposed create_task change presented to the user for approval."""

    type: Literal["create_task"] = "create_task"
    title: str
    description: str | None = None
    column_id: Literal["backlog", "todo", "in_progress", "done"] = "todo"
    project_id: uuid.UUID | None = None
    project_name: str | None = None
    checklist: list[ChecklistItem] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate(self) -> "CreateTaskChange":
        self.title = self.title.strip()
        if not self.title:
            raise ValueError("title cannot be blank")
        self.checklist = _strip_blank_checklist_items(self.checklist)
        return self


class MoveTaskChange(SQLModel):
    """A single proposed move_task change presented to the user for approval."""

    type: Literal["move_task"] = "move_task"
    task_id: uuid.UUID
    title: str
    from_column_id: Literal["backlog", "todo", "in_progress", "done"]
    to_column_id: Literal["backlog", "todo", "in_progress", "done"]
    project_name: str | None = None
    position: int | None = None

    @model_validator(mode="after")
    def validate(self) -> "MoveTaskChange":
        self.title = self.title.strip()
        if self.position is not None and self.position < 0:
            raise ValueError("position cannot be negative")
        return self


class UpdateTaskChange(SQLModel):
    """A single proposed update_task change presented to the user for approval.

    The tool may supply only the fields the user wants to change; the graph's
    tool_node merges in the current task state so this change carries the full
    payload required by the full-replace PATCH endpoint.
    """

    type: Literal["update_task"] = "update_task"
    task_id: uuid.UUID
    title: str
    description: str | None = None
    project_id: uuid.UUID | None = None
    project_name: str | None = None
    checklist: list[ChecklistItem] = Field(default_factory=list)
    due_date: date | None = None

    @model_validator(mode="after")
    def validate(self) -> "UpdateTaskChange":
        self.title = self.title.strip()
        if not self.title:
            raise ValueError("title cannot be blank")
        self.checklist = _strip_blank_checklist_items(self.checklist)
        return self


BoardChange = Union[CreateTaskChange, MoveTaskChange, UpdateTaskChange]


class ProposedDiff(SQLModel):
    """A bundle of changes shown to the user in the approval interrupt."""

    changes: list[BoardChange] = Field(default_factory=list)


class AppliedResult(SQLModel):
    """The result of applying an approved diff."""

    created_tasks: list[Task] = Field(default_factory=list)
    moved_tasks: list[Task] = Field(default_factory=list)
    updated_tasks: list[Task] = Field(default_factory=list)


class AgentState(TypedDict):
    """LangGraph state carrier for the HITL agent.

    Messages carry the conversation. Proposed changes are produced by the tool
    node. The approved flag is set when the user resumes from the interrupt.
    Applied results record what the apply node persisted. Draft accumulates
    partial task details so the agent does not have to rely on the LLM's memory.
    """

    messages: Annotated[list, add_messages]
    proposed_changes: list[BoardChange]
    approved: bool | None
    # Applied results are stored as plain dicts to avoid SQLAlchemy object
    # serialization issues when LangGraph checkpoints the state.
    applied_results: list[dict]
    applied_moved_results: list[dict]
    applied_updated_results: list[dict]
    draft: dict | None
