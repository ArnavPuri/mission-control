"""
WebSocket endpoint for real-time dashboard updates.
Dashboard connects here to get live agent status, new tasks, etc.
"""

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
    for ws in list(_connections):  # copy: clients may connect while we await
        try:
            await ws.send_text(message)
        except Exception:
            disconnected.add(ws)
    _connections.difference_update(disconnected)


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    _connections.add(websocket)
    try:
        while True:
            # Keep the connection open; the dashboard doesn't send anything
            await websocket.receive_text()
    except WebSocketDisconnect:
        _connections.discard(websocket)
