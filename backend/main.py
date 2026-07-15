import uuid
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException
from sqlalchemy import func
from sqlmodel import Session, select

from db import create_db_and_tables, get_session
from models import Task, TaskCreate, TaskMove, WorkBlock, WorkBlockCreate


@asynccontextmanager
async def lifespan(app: FastAPI):
    create_db_and_tables()
    yield


app = FastAPI(lifespan=lifespan)


@app.get("/health")
def read_health():
    return {"ok": True}


@app.get("/tasks", response_model=list[Task])
def list_tasks(session: Session = Depends(get_session)):
    return session.exec(
        select(Task).order_by(Task.column_id, Task.position, Task.created_at)
    ).all()


@app.post("/tasks", response_model=Task, status_code=201)
def create_task(payload: TaskCreate, session: Session = Depends(get_session)):
    next_position = session.exec(
        select(func.count())
        .select_from(Task)
        .where(Task.column_id == payload.column_id)
    ).one()
    task = Task(**payload.model_dump(), position=next_position)
    session.add(task)
    session.commit()
    session.refresh(task)
    return task


def column_tasks(session: Session, column_id: str) -> list[Task]:
    return list(
        session.exec(
            select(Task)
            .where(Task.column_id == column_id)
            .order_by(Task.position, Task.created_at)
        ).all()
    )


@app.patch("/tasks/{task_id}/move", response_model=Task)
def move_task(
    task_id: uuid.UUID,
    payload: TaskMove,
    session: Session = Depends(get_session),
):
    task = session.get(Task, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="task not found")

    source = [t for t in column_tasks(session, task.column_id) if t.id != task.id]
    target = (
        source
        if payload.column_id == task.column_id
        else column_tasks(session, payload.column_id)
    )
    target.insert(min(payload.position, len(target)), task)
    task.column_id = payload.column_id

    # Reindex both affected columns so positions stay dense and ordered.
    for index, t in enumerate(source):
        t.position = index
    for index, t in enumerate(target):
        t.position = index
    session.add_all(source)
    session.add_all(target)
    session.commit()
    session.refresh(task)
    return task


@app.post(
    "/tasks/{task_id}/work-blocks", response_model=WorkBlock, status_code=201
)
def create_work_block(
    task_id: uuid.UUID,
    payload: WorkBlockCreate,
    session: Session = Depends(get_session),
):
    if session.get(Task, task_id) is None:
        raise HTTPException(status_code=404, detail="task not found")
    block = WorkBlock(task_id=task_id, **payload.model_dump())
    session.add(block)
    session.commit()
    session.refresh(block)
    return block


@app.get("/tasks/{task_id}/work-blocks", response_model=list[WorkBlock])
def list_work_blocks(task_id: uuid.UUID, session: Session = Depends(get_session)):
    if session.get(Task, task_id) is None:
        raise HTTPException(status_code=404, detail="task not found")
    return session.exec(
        select(WorkBlock)
        .where(WorkBlock.task_id == task_id)
        .order_by(WorkBlock.started_at, WorkBlock.created_at)
    ).all()


@app.delete("/tasks/{task_id}", status_code=204)
def delete_task(task_id: uuid.UUID, session: Session = Depends(get_session)):
    task = session.get(Task, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="task not found")

    remaining = [t for t in column_tasks(session, task.column_id) if t.id != task.id]
    session.delete(task)
    for index, t in enumerate(remaining):
        t.position = index
    session.add_all(remaining)
    session.commit()
