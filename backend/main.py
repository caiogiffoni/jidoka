import uuid
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException
from sqlalchemy import func
from sqlmodel import Session, select

from db import create_db_and_tables, get_session
from models import Task, TaskCreate, TaskMove


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
