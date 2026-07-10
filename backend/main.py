from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from sqlalchemy import func
from sqlmodel import Session, select

from db import create_db_and_tables, get_session
from models import Task, TaskCreate


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
