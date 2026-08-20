"""Task endpoints."""

import uuid

from fastapi import APIRouter, Depends, Query, Request
from sqlmodel import Session, select

import auth
from db import get_session
from models import Task, TaskArchive, TaskCreate, TaskMove, TaskUpdate, User, WorkBlock, WorkBlockCreate
from rate_limit import limiter
from services import (
    column_tasks,
    create_task_service,
    get_project_or_404,
    get_task_or_404,
    move_task_service,
    reindex,
    update_task_service,
)

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.get("", response_model=list[Task])
def list_tasks(
    include_archived: bool = Query(default=False),
    current_user: User = Depends(auth.get_current_user),
    session: Session = Depends(get_session),
):
    query = (
        select(Task)
        .where(Task.user_id == current_user.id)
        .order_by(Task.column_id, Task.position, Task.created_at)
    )
    if not include_archived:
        query = query.where(Task.archived.is_(False))
    return session.exec(query).all()


@router.post("", response_model=Task, status_code=201)
@limiter.limit("1000/minute")
def create_task(
    request: Request,
    payload: TaskCreate,
    current_user: User = Depends(auth.get_current_user),
    session: Session = Depends(get_session),
):
    return create_task_service(session, current_user.id, payload)


@router.patch("/{task_id}", response_model=Task)
def update_task(
    task_id: uuid.UUID,
    payload: TaskUpdate,
    current_user: User = Depends(auth.get_current_user),
    session: Session = Depends(get_session),
):
    return update_task_service(session, current_user.id, task_id, payload)


@router.patch("/{task_id}/move", response_model=Task)
def move_task(
    task_id: uuid.UUID,
    payload: TaskMove,
    current_user: User = Depends(auth.get_current_user),
    session: Session = Depends(get_session),
):
    return move_task_service(
        session,
        current_user.id,
        task_id,
        payload.column_id,
        payload.position,
    )


@router.patch("/{task_id}/archive", response_model=Task)
def set_task_archived(
    task_id: uuid.UUID,
    payload: TaskArchive,
    current_user: User = Depends(auth.get_current_user),
    session: Session = Depends(get_session),
):
    task = get_task_or_404(session, task_id, current_user.id)
    if task.archived == payload.archived:
        return task

    if payload.archived:
        remaining = [
            t
            for t in column_tasks(session, task.column_id, current_user.id)
            if t.id != task.id
        ]
        task.archived = True
        reindex(remaining)
        session.add_all(remaining)
    else:
        new_position = len(column_tasks(session, task.column_id, current_user.id))
        task.archived = False
        task.position = new_position

    session.add(task)
    session.commit()
    session.refresh(task)
    return task


@router.delete("/{task_id}", status_code=204)
def delete_task(
    task_id: uuid.UUID,
    current_user: User = Depends(auth.get_current_user),
    session: Session = Depends(get_session),
):
    task = get_task_or_404(session, task_id, current_user.id)

    remaining = [
        t
        for t in column_tasks(session, task.column_id, current_user.id)
        if t.id != task.id
    ]
    session.delete(task)
    reindex(remaining)
    session.add_all(remaining)
    session.commit()


@router.post("/{task_id}/work-blocks", response_model=WorkBlock, status_code=201)
@limiter.limit("1000/minute")
def create_work_block(
    request: Request,
    task_id: uuid.UUID,
    payload: WorkBlockCreate,
    current_user: User = Depends(auth.get_current_user),
    session: Session = Depends(get_session),
):
    get_task_or_404(session, task_id, current_user.id)
    data = payload.model_dump()
    if data["minutes"] is None:
        duration = payload.ended_at - payload.started_at
        data["minutes"] = max(1, round(duration.total_seconds() / 60))
    block = WorkBlock(task_id=task_id, **data)
    session.add(block)
    session.commit()
    session.refresh(block)
    return block


@router.get("/{task_id}/work-blocks", response_model=list[WorkBlock])
def list_work_blocks(
    task_id: uuid.UUID,
    current_user: User = Depends(auth.get_current_user),
    session: Session = Depends(get_session),
):
    get_task_or_404(session, task_id, current_user.id)
    return session.exec(
        select(WorkBlock)
        .where(WorkBlock.task_id == task_id)
        .order_by(WorkBlock.started_at, WorkBlock.created_at)
    ).all()
