"""Shared service helpers used by FastAPI endpoints and the agent apply node.

These functions intentionally live outside the endpoint modules so the agent
graph can call the same DB code path as the UI.
"""

import uuid

from fastapi import HTTPException
from sqlalchemy import func
from sqlmodel import Session, select

import auth
from db import get_session
from models import Project, Task, TaskCreate


def get_task_or_404(
    session: Session, task_id: uuid.UUID, user_id: uuid.UUID | None = None
) -> Task:
    task = session.get(Task, task_id)
    if task is None or (user_id is not None and task.user_id != user_id):
        raise HTTPException(status_code=404, detail="task not found")
    return task


def get_project_or_404(
    session: Session, project_id: uuid.UUID, user_id: uuid.UUID | None = None
) -> Project:
    project = session.get(Project, project_id)
    if project is None or (user_id is not None and project.user_id != user_id):
        raise HTTPException(status_code=404, detail="project not found")
    return project


def column_tasks(session: Session, column_id: str, user_id: uuid.UUID) -> list[Task]:
    return list(
        session.exec(
            select(Task)
            .where(
                Task.column_id == column_id,
                Task.archived.is_(False),
                Task.user_id == user_id,
            )
            .order_by(Task.position, Task.created_at)
        ).all()
    )


def reindex(tasks: list[Task]) -> None:
    for index, t in enumerate(tasks):
        t.position = index


def create_task_service(session: Session, user_id: uuid.UUID, payload: TaskCreate) -> Task:
    """Create a task using the same logic as the manual POST /tasks endpoint.

    Extracted so the agent's apply node and the API share one code path.
    """
    if payload.project_id is not None:
        get_project_or_404(session, payload.project_id, user_id)
    next_position = session.exec(
        select(func.count())
        .select_from(Task)
        .where(
            Task.column_id == payload.column_id,
            Task.archived.is_(False),
            Task.user_id == user_id,
        )
    ).one()
    task = Task(**payload.model_dump(), user_id=user_id, position=next_position)
    session.add(task)
    session.commit()
    session.refresh(task)
    return task


def list_tasks_service(
    session: Session,
    user_id: uuid.UUID,
    column_id: str | None = None,
    include_archived: bool = False,
) -> list[Task]:
    """List tasks for a user, matching GET /tasks behavior."""
    query = (
        select(Task)
        .where(Task.user_id == user_id)
        .order_by(Task.column_id, Task.position, Task.created_at)
    )
    if not include_archived:
        query = query.where(Task.archived.is_(False))
    if column_id is not None:
        query = query.where(Task.column_id == column_id)
    return list(session.exec(query).all())


def get_task_service(session: Session, task_id: uuid.UUID, user_id: uuid.UUID) -> Task:
    """Fetch a single task, verifying ownership."""
    return get_task_or_404(session, task_id, user_id)


def list_projects_service(session: Session, user_id: uuid.UUID) -> list[Project]:
    """List projects for a user, matching GET /projects behavior."""
    return list(
        session.exec(
            select(Project)
            .where(Project.user_id == user_id)
            .order_by(Project.created_at)
        ).all()
    )


def move_task_service(
    session: Session,
    user_id: uuid.UUID,
    task_id: uuid.UUID,
    column_id: str,
    position: int | None = None,
) -> Task:
    """Move a task to a column and/or position, matching PATCH /tasks/{id}/move."""
    if column_id not in {"backlog", "todo", "in_progress", "done"}:
        raise HTTPException(status_code=422, detail="invalid column_id")

    task = get_task_or_404(session, task_id, user_id)

    source = [
        t
        for t in column_tasks(session, task.column_id, user_id)
        if t.id != task.id
    ]
    target = (
        source
        if column_id == task.column_id
        else column_tasks(session, column_id, user_id)
    )
    insert_position = min(position if position is not None else len(target), len(target))
    target.insert(insert_position, task)
    task.column_id = column_id

    reindex(source)
    reindex(target)
    session.add_all(source)
    session.add_all(target)
    session.commit()
    session.refresh(task)
    return task


__all__ = [
    "auth",
    "get_session",
    "get_task_or_404",
    "get_project_or_404",
    "column_tasks",
    "reindex",
    "create_task_service",
    "list_tasks_service",
    "get_task_service",
    "list_projects_service",
    "move_task_service",
]
