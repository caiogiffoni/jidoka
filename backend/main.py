import os
from contextlib import asynccontextmanager

from fastapi import FastAPI

import auth
from agent.routes import router as agent_router
from db import create_db_and_tables
from routers import health, projects, tasks, work_blocks


@asynccontextmanager
async def lifespan(app: FastAPI):
    if not os.environ.get("JWT_SECRET_KEY"):
        raise RuntimeError("JWT_SECRET_KEY environment variable is not set")
    create_db_and_tables()
    yield


app = FastAPI(lifespan=lifespan)
app.include_router(auth.router)
app.include_router(health.router)
app.include_router(tasks.router)
app.include_router(projects.router)
app.include_router(work_blocks.router)
app.include_router(agent_router)
