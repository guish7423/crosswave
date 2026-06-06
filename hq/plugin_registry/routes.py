"""FastAPI router for Plugin Registry."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from .models import PluginRegisterRequest, PluginStatus
from .registry import get_registry

router = APIRouter(prefix="/api/hq/plugins", tags=["plugins"])


@router.get("")
async def list_plugins():
    registry = get_registry()
    return {"plugins": [p.model_dump() for p in registry.list()]}


@router.get("/{plugin_id}")
async def get_plugin(plugin_id: str):
    registry = get_registry()
    info = registry.get(plugin_id)
    if info is None:
        raise HTTPException(status_code=404, detail="Plugin not found")
    return info.model_dump()


@router.post("/register")
async def register_plugin(req: PluginRegisterRequest):
    registry = get_registry()
    info = registry.register(req)
    return info.model_dump()


@router.post("/{plugin_id}/heartbeat")
async def plugin_heartbeat(plugin_id: str):
    registry = get_registry()
    info = registry.heartbeat(plugin_id)
    if info is None:
        raise HTTPException(status_code=404, detail="Plugin not found")
    return info.model_dump()


@router.delete("/{plugin_id}")
async def unregister_plugin(plugin_id: str):
    registry = get_registry()
    if not registry.unregister(plugin_id):
        raise HTTPException(status_code=404, detail="Plugin not found")
    return {"ok": True}


@router.post("/check")
async def check_all_health():
    registry = get_registry()
    results = await registry.check_all_health()
    return {"results": results}
