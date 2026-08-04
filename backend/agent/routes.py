"""FastAPI router for the agent SSE endpoint."""

from fastapi import APIRouter

router = APIRouter(prefix="/agent", tags=["agent"])
