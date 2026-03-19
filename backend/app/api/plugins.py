"""Plugin management API."""

from fastapi import APIRouter, HTTPException
from app.plugins.loader import plugin_manager

router = APIRouter()


@router.get("")
async def list_plugins():
    """List installed plugins with status."""
    return plugin_manager.list_plugins()


@router.post("/{name}/enable")
async def enable_plugin(name: str):
    """Enable a plugin."""
    if not plugin_manager.enable(name):
        raise HTTPException(status_code=404, detail="Plugin not found")
    return {"enabled": True, "name": name}


@router.post("/{name}/disable")
async def disable_plugin(name: str):
    """Disable a plugin."""
    if not plugin_manager.disable(name):
        raise HTTPException(status_code=404, detail="Plugin not found")
    return {"disabled": True, "name": name}
