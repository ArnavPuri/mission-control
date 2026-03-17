"""
WebSocket endpoint for real-time dashboard updates.
Dashboard connects here to get live agent status, new tasks, etc.
"""

import asyncio
import json
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from typing import Set

router = APIRouter()

# Connected dashboard clients
_connections: Set[WebSocket] = set()


async def broadcast(event_type: str, data: dict):
    """Broadcast an event to all connected dashboard clients."""
    message = json.dumps({"type": event_type, "data": data})
    disconnected = set()
    for ws in _connections:
        try:
            await ws.send_text(message)
        except Exception:
            disconnected.add(ws)
    _connections -= disconnected


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    _connections.add(websocket)
    try:
        while True:
            # Keep connection alive, handle any incoming messages
            data = await websocket.receive_text()
            # Could handle dashboard commands here (e.g., subscribe to specific agents)
    except WebSocketDisconnect:
        _connections.discard(websocket)
