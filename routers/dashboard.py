import asyncio
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from services.memory_service import memory_service
from services.context_service import context_service
from routers import broadcast

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@router.get("/state")
async def get_state(session_id: str = "default"):
    """Current agent state — scene, context, and the most recent decision."""
    scene = await memory_service.get_scene(session_id)
    history = await memory_service.get_history(session_id, limit=1)

    # Build the full context the same way agents do (uses scene + history + stored context)
    built_context = await context_service.build(session_id, scene or {})

    return {
        "session_id": session_id,
        "current_scene": scene,
        "context": built_context,   # last_people_count, recent_hazards, narration_history, scene_changed
        "latest_decision": history[0] if history else None,
    }


@router.get("/history")
async def get_history(session_id: str = "default", limit: int = 20):
    """Full decision log — detected elements, suppressed elements, narration, and agent scores."""
    history = await memory_service.get_history(session_id, limit=limit)

    return {
        "session_id": session_id,
        "total": len(history),
        "decisions": history,
    }


@router.delete("/history")
async def clear_history(session_id: str = "default"):
    """Clear decision history and context for a session (useful for demo resets)."""
    await memory_service.clear_session(session_id)
    return {"cleared": True, "session_id": session_id}


@router.websocket("/ws")
async def dashboard_ws(websocket: WebSocket):
    """
    Real-time push feed for the agent dashboard.

    Subscribe here — the server pushes every frame's agent decision
    the moment it is processed, without the client polling.

    Receives: { timestamp, session_id, detected_elements, suppressed_elements,
                chosen_narration, priority_level, agent_decisions, scene_graph }
    """
    await websocket.accept()
    broadcast.subscribe(websocket)
    try:
        while True:
            await asyncio.sleep(30)
            await websocket.send_json({"heartbeat": True})
    except WebSocketDisconnect:
        pass
    finally:
        broadcast.unsubscribe(websocket)
