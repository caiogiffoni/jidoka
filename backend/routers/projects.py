"""Project endpoints."""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlmodel import Session, select

import auth
from db import get_session
from models import Project, ProjectCreate, ProjectUpdate, Task, User
from services import get_project_or_404

router = APIRouter(prefix="/projects", tags=["projects"])


@router.post("", response_model=Project, status_code=201)
def create_project(
    payload: ProjectCreate,
    current_user: User = Depends(auth.get_current_user),
    session: Session = Depends(get_session),
):
    # model_dump() recursively converts daily_template into a plain dict (or
    # None) so the JSON column can serialize it - a bare DailyTemplate
    # instance isn't natively JSON-serializable.
    project = Project(**payload.model_dump(), user_id=current_user.id)
    session.add(project)
    session.commit()
    session.refresh(project)
    return project


@router.get("", response_model=list[Project])
def list_projects(
    current_user: User = Depends(auth.get_current_user),
    session: Session = Depends(get_session),
):
    return session.exec(
        select(Project)
        .where(Project.user_id == current_user.id)
        .order_by(Project.created_at)
    ).all()


@router.patch("/{project_id}", response_model=Project)
def update_project(
    project_id: uuid.UUID,
    payload: ProjectUpdate,
    current_user: User = Depends(auth.get_current_user),
    session: Session = Depends(get_session),
):
    project = get_project_or_404(session, project_id, current_user.id)
    project.name = payload.name
    project.description = payload.description
    project.daily_enabled = payload.daily_enabled
    project.daily_template = (
        payload.daily_template.model_dump() if payload.daily_template else None
    )
    session.add(project)
    session.commit()
    session.refresh(project)
    return project


@router.post("/daily-tasks/generate", response_model=list[Task], status_code=201)
def generate_daily_tasks(
    current_user: User = Depends(auth.get_current_user),
    session: Session = Depends(get_session),
):
    today = datetime.now(timezone.utc).date()
    today_iso = today.isoformat()
    due = [
        p
        for p in session.exec(
            select(Project).where(
                Project.daily_enabled.is_(True),
                Project.user_id == current_user.id,
            )
        ).all()
        if p.daily_template is not None and p.daily_last_generated != today_iso
    ]
    if not due:
        return []

    from sqlalchemy import func

    next_position = session.exec(
        select(func.count())
        .select_from(Task)
        .where(
            Task.column_id == "todo",
            Task.archived.is_(False),
            Task.user_id == current_user.id,
        )
    ).one()

    created: list[Task] = []
    for project in due:
        # daily_template comes back from the JSON column as a plain dict,
        # not a DailyTemplate instance - dict access, not attribute access.
        template = project.daily_template
        title = f"Daily - {today:%d-%m-%y} - {project.name}"
        if template.get("title"):
            title += f" - {template['title']}"
        task = Task(
            title=title,
            description=template.get("description"),
            column_id="todo",
            project_id=project.id,
            user_id=current_user.id,
            position=next_position,
            checklist=[
                {"text": item, "checked": False} for item in template["checklist"]
            ],
        )
        next_position += 1
        project.daily_last_generated = today_iso
        session.add(task)
        session.add(project)
        created.append(task)

    session.commit()
    for task in created:
        session.refresh(task)
    return created


@router.delete("/{project_id}", status_code=204)
def delete_project(
    project_id: uuid.UUID,
    current_user: User = Depends(auth.get_current_user),
    session: Session = Depends(get_session),
):
    project = get_project_or_404(session, project_id, current_user.id)
    session.delete(project)
    session.commit()
