"""
Shared real-time broadcast bus.

stream.py  → calls push() after every processed frame
dashboard.py → manages subscriber WebSockets

Kept in its own module to avoid circular imports.
"""
from fastapi import WebSocket

_subscribers: list[WebSocket] = []


def subscribe(ws: WebSocket):
    _subscribers.append(ws)


def unsubscribe(ws: WebSocket):
    if ws in _subscribers:
        _subscribers.remove(ws)


async def push(data: dict):
    """Broadcast data to all dashboard WebSocket subscribers."""
    dead = []
    for ws in _subscribers:
        try:
            await ws.send_json(data)
        except Exception:
            dead.append(ws)
    for ws in dead:
        unsubscribe(ws)
