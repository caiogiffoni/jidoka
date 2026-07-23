import uuid
from contextlib import asynccontextmanager
from datetime import datetime, time, timedelta, timezone

from fastapi import Depends, FastAPI, HTTPException, Query
from sqlalchemy import func
from sqlmodel import Session, select

from db import create_db_and_tables, get_session
from models import (
    DailyProjectStat,
    Project,
    ProjectCreate,
    ProjectUpdate,
    Task,
    TaskArchive,
    TaskCreate,
    TaskMove,
    TaskUpdate,
    WorkBlock,
    WorkBlockCreate,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    create_db_and_tables()
    yield


app = FastAPI(lifespan=lifespan)


@app.get("/health")
def read_health():
    return {"ok": True}


@app.get("/tasks", response_model=list[Task])
def list_tasks(
    include_archived: bool = Query(default=False),
    session: Session = Depends(get_session),
):
    query = select(Task).order_by(Task.column_id, Task.position, Task.created_at)
    if not include_archived:
        query = query.where(Task.archived.is_(False))
    return session.exec(query).all()


@app.post("/tasks", response_model=Task, status_code=201)
def create_task(payload: TaskCreate, session: Session = Depends(get_session)):
    if payload.project_id is not None and session.get(Project, payload.project_id) is None:
        raise HTTPException(status_code=404, detail="project not found")
    next_position = session.exec(
        select(func.count())
        .select_from(Task)
        .where(Task.column_id == payload.column_id, Task.archived.is_(False))
    ).one()
    task = Task(**payload.model_dump(), position=next_position)
    session.add(task)
    session.commit()
    session.refresh(task)
    return task


@app.patch("/tasks/{task_id}", response_model=Task)
def update_task(
    task_id: uuid.UUID,
    payload: TaskUpdate,
    session: Session = Depends(get_session),
):
    task = session.get(Task, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="task not found")
    if payload.project_id is not None and session.get(Project, payload.project_id) is None:
        raise HTTPException(status_code=404, detail="project not found")
    task.title = payload.title
    task.description = payload.description
    task.project_id = payload.project_id
    session.add(task)
    session.commit()
    session.refresh(task)
    return task


def column_tasks(session: Session, column_id: str) -> list[Task]:
    return list(
        session.exec(
            select(Task)
            .where(Task.column_id == column_id, Task.archived.is_(False))
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


@app.patch("/tasks/{task_id}/archive", response_model=Task)
def set_task_archived(
    task_id: uuid.UUID,
    payload: TaskArchive,
    session: Session = Depends(get_session),
):
    task = session.get(Task, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="task not found")
    if task.archived == payload.archived:
        return task

    if payload.archived:
        remaining = [t for t in column_tasks(session, task.column_id) if t.id != task.id]
        task.archived = True
        for index, t in enumerate(remaining):
            t.position = index
        session.add_all(remaining)
    else:
        new_position = len(column_tasks(session, task.column_id))
        task.archived = False
        task.position = new_position

    session.add(task)
    session.commit()
    session.refresh(task)
    return task


@app.post("/projects", response_model=Project, status_code=201)
def create_project(payload: ProjectCreate, session: Session = Depends(get_session)):
    project = Project(name=payload.name, description=payload.description)
    session.add(project)
    session.commit()
    session.refresh(project)
    return project


@app.get("/projects", response_model=list[Project])
def list_projects(session: Session = Depends(get_session)):
    return session.exec(select(Project).order_by(Project.created_at)).all()


@app.patch("/projects/{project_id}", response_model=Project)
def update_project(
    project_id: uuid.UUID,
    payload: ProjectUpdate,
    session: Session = Depends(get_session),
):
    project = session.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="project not found")
    project.name = payload.name
    project.description = payload.description
    session.add(project)
    session.commit()
    session.refresh(project)
    return project


@app.delete("/projects/{project_id}", status_code=204)
def delete_project(project_id: uuid.UUID, session: Session = Depends(get_session)):
    project = session.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="project not found")
    session.delete(project)
    session.commit()


@app.get("/work-blocks/stats/daily", response_model=list[DailyProjectStat])
def daily_work_block_stats(
    days: int = Query(default=7, ge=1, le=90),
    session: Session = Depends(get_session),
):
    today = datetime.now(timezone.utc).date()
    since = datetime.combine(
        today - timedelta(days=days - 1), time.min, tzinfo=timezone.utc
    )

    day_bucket = func.date_trunc(
        "day", func.coalesce(WorkBlock.started_at, WorkBlock.created_at)
    )
    minutes_expr = func.coalesce(
        WorkBlock.minutes,
        func.extract("epoch", WorkBlock.ended_at - WorkBlock.started_at) / 60,
    )

    rows = session.exec(
        select(
            day_bucket.label("day"),
            Task.project_id.label("project_id"),
            Project.name.label("project_name"),
            func.sum(minutes_expr).label("minutes"),
        )
        .select_from(WorkBlock)
        .join(Task, Task.id == WorkBlock.task_id)
        .join(Project, Project.id == Task.project_id, isouter=True)
        .where(func.coalesce(WorkBlock.started_at, WorkBlock.created_at) >= since)
        .group_by(day_bucket, Task.project_id, Project.name)
        .order_by(day_bucket)
    ).all()

    return [
        DailyProjectStat(
            date=row.day.date().isoformat(),
            project_id=row.project_id,
            project_name=row.project_name,
            minutes=round(float(row.minutes), 2),
        )
        for row in rows
    ]


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
    data = payload.model_dump()
    if data["minutes"] is None:
        duration = payload.ended_at - payload.started_at
        data["minutes"] = max(1, round(duration.total_seconds() / 60))
    block = WorkBlock(task_id=task_id, **data)
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
