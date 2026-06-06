"""Workflow management API routes."""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(prefix="/api/hq/workflows", tags=["workflows"])

_WORKFLOWS: list[dict] = []


def register(name: str, description: str) -> None:
    _WORKFLOWS.append({"name": name, "description": description})


@router.get("")
async def list_workflows():
    return {"workflows": _WORKFLOWS}
