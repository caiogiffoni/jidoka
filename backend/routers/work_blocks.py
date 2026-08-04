"""Work block aggregate endpoints."""

from datetime import datetime, time, timedelta, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlmodel import Session, select

import auth
from db import get_session
from models import DailyProjectStat, Project, Task, User, WorkBlock

router = APIRouter(prefix="/work-blocks", tags=["work-blocks"])


@router.get("/stats/daily", response_model=list[DailyProjectStat])
def daily_work_block_stats(
    days: int = Query(default=7, ge=1, le=90),
    current_user: User = Depends(auth.get_current_user),
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
        .where(
            func.coalesce(WorkBlock.started_at, WorkBlock.created_at) >= since,
            Task.user_id == current_user.id,
        )
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
