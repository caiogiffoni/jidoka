"""State schemas and change types for the HITL agent graph.

These objects are the contract between the agent's nodes, the SSE endpoint,
and the frontend diff approval UI.
"""

import uuid
from typing import Literal, TypedDict

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
    checklist: list[ChecklistItem] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate(self) -> "CreateTaskChange":
        self.title = self.title.strip()
        if not self.title:
            raise ValueError("title cannot be blank")
        self.checklist = _strip_blank_checklist_items(self.checklist)
        return self


class ProposedDiff(SQLModel):
    """A bundle of changes shown to the user in the approval interrupt."""

    changes: list[CreateTaskChange] = Field(default_factory=list)


class AppliedResult(SQLModel):
    """The result of applying an approved diff."""

    created_tasks: list[Task] = Field(default_factory=list)


class AgentState(TypedDict):
    """LangGraph state carrier for the HITL agent.

    Messages carry the conversation. Proposed changes are produced by the tool
    node. The approved flag is set when the user resumes from the interrupt.
    Applied results record what the apply node persisted.
    """

    messages: list
    proposed_changes: list[CreateTaskChange]
    approved: bool | None
    applied_results: list[Task]
