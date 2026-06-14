import time
import json
import base64
import asyncio
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException
from pydantic import BaseModel
from typing import Optional
from services.vision_service import get_scene
from services.memory_service import memory_service
from services.speech_service import text_to_speech
from services.camera_service import camera_service
from agents.orchestrator import run_pipeline
from routers import broadcast

router = APIRouter(prefix="/stream", tags=["Stream"])

# Connected clients waiting for autonomous camera results
_camera_clients: list[WebSocket] = []


# ── Request models ────────────────────────────────────────────────────────────

class FrameRequest(BaseModel):
    frame_base64: str           # JPEG frame from camera, base64-encoded
    session_id: str = "default"
    voice: str = "nova"
    return_audio: bool = True


class CameraStartRequest(BaseModel):
    session_id: str = "default"
    camera_index: int = 0      # 0 = default device camera
    fps_limit: float = 0.5     # Frames/sec sent to AI (0.5 = 1 per 2 seconds)
    voice: str = "nova"


# ── Helpers ───────────────────────────────────────────────────────────────────

def _build_dashboard_entry(session_id: str, pipeline_result: dict, scene_dict: dict) -> dict:
    triage = pipeline_result.get("triage_decision") or {}
    winner = triage.get("winner") or {}
    narration = pipeline_result.get("final_narration") or ""

    all_results = [
        pipeline_result.get("hazard_result") or {},
        pipeline_result.get("navigation_result") or {},
        pipeline_result.get("social_result") or {},
        pipeline_result.get("ocr_result") or {},
        pipeline_result.get("suggestion_result") or {},
    ]

    agent_decisions = [
        {
            "agent": r.get("agent", "unknown"),
            "priority": r.get("priority", 5),
            "score": round(r.get("score", 0.0), 3),
            "message": r.get("message", ""),
            "suppressed": r.get("message", "") in triage.get("suppressed", []),
        }
        for r in all_results
        if r.get("agent")
    ]

    return {
        "timestamp": time.time(),
        "session_id": session_id,
        "detected_elements": triage.get("detected", []),
        "suppressed_elements": triage.get("suppressed", []),
        "chosen_narration": narration,
        "priority_level": winner.get("priority", 5),
        "reasoning": (
            f"Agent '{winner.get('agent', 'none')}' won with score {winner.get('score', 0):.2f}"
            if winner
            else "No actionable content detected"
        ),
        "agent_decisions": agent_decisions,
        "scene_graph": scene_dict,
    }


async def _process_frame(session_id: str, frame_b64: str, voice: str = "nova") -> dict:
    """Full pipeline: frame → scene → agents → narration → TTS."""
    scene = await get_scene(frame_b64)
    scene_dict = scene.model_dump()

    # save_scene is called AFTER run_pipeline so that context_service.build()
    # reads the PREVIOUS frame's scene when detecting scene_changed.
    pipeline_result = await run_pipeline(
        session_id=session_id,
        frame_base64=frame_b64,
        scene_graph=scene_dict,
    )

    await memory_service.save_scene(session_id, scene_dict)

    narration = pipeline_result.get("final_narration") or ""
    triage = pipeline_result.get("triage_decision") or {}
    winner = triage.get("winner") or {}
    memory_context = pipeline_result.get("memory_context") or {}

    entry = _build_dashboard_entry(session_id, pipeline_result, scene_dict)
    await memory_service.add_history(session_id, entry)
    await broadcast.push(entry)

    # AI autonomously triggers TTS — no separate call needed from client
    audio_b64 = None
    if narration:
        try:
            audio_bytes = await text_to_speech(narration, voice)
            audio_b64 = base64.b64encode(audio_bytes).decode("utf-8")
        except Exception:
            audio_b64 = None

    return {
        "narration": narration,
        "should_speak": bool(narration),
        "audio_base64": audio_b64,
        "audio_format": "mp3",
        "priority": winner.get("priority", 5),
        "winner_agent": winner.get("agent"),
        "suppressed_count": len(triage.get("suppressed", [])),
        "scene_graph": scene_dict,
        "context": memory_context,   # what the agents actually saw: last_people_count, recent_hazards, etc.
        "dashboard": entry,
    }


async def _broadcast(result: dict):
    """Push result to all connected camera WebSocket subscribers."""
    if not _camera_clients:
        return
    dead = []
    for ws in list(_camera_clients):  # snapshot to avoid mutation during iteration
        try:
            await ws.send_json(result)
        except Exception:
            dead.append(ws)
    for ws in dead:
        try:
            _camera_clients.remove(ws)
        except ValueError:
            pass


# ── HTTP: single frame ────────────────────────────────────────────────────────

@router.post("/frame")
async def upload_frame(request: FrameRequest):
    """
    Submit one camera frame. AI decides what to say and returns audio.
    Play audio_base64 on device when should_speak is true.
    """
    start = time.time()
    try:
        result = await _process_frame(request.session_id, request.frame_base64, request.voice)
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Pipeline failed: {e}")

    if not request.return_audio:
        result.pop("audio_base64", None)

    result["latency_ms"] = round((time.time() - start) * 1000)
    return result


# ── WebSocket: client-driven stream (client sends frames) ─────────────────────

@router.websocket("/ws/{session_id}")
async def websocket_stream(websocket: WebSocket, session_id: str):
    """
    Real-time stream where the client (mobile app) sends camera frames.

    Client sends: { "frame_base64": "<JPEG b64>", "voice": "nova" }
    Server sends: { "narration": "...", "should_speak": bool,
                    "audio_base64": "<mp3 b64>", "priority": int, "winner_agent": "..." }

    When should_speak is false — AI decided silence, skip audio playback.
    """
    await websocket.accept()
    try:
        while True:
            raw = await websocket.receive_text()
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError:
                await websocket.send_json({"error": "Invalid JSON"})
                continue

            frame_b64 = payload.get("frame_base64", "")
            if not frame_b64:
                await websocket.send_json({"error": "Missing frame_base64"})
                continue

            try:
                result = await _process_frame(session_id, frame_b64, payload.get("voice", "nova"))
                result.pop("dashboard", None)
                await websocket.send_json(result)
            except Exception as e:
                await websocket.send_json({"error": str(e), "should_speak": False})

    except WebSocketDisconnect:
        pass
    except Exception as e:
        try:
            await websocket.send_json({"error": str(e)})
            await websocket.close()
        except Exception:
            pass


# ── WebSocket: binary audio stream (native apps) ──────────────────────────────

@router.websocket("/ws-audio/{session_id}")
async def websocket_audio_stream(websocket: WebSocket, session_id: str):
    """
    Same as /ws but sends raw MP3 bytes after the JSON metadata frame.

    Client sends:  JSON  { "frame_base64": "...", "voice": "nova" }
    Server sends:  JSON  { "narration": "...", "should_speak": bool, ... }
                   then: binary MP3 bytes (only when should_speak is true)
    """
    await websocket.accept()
    try:
        while True:
            raw = await websocket.receive_text()
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError:
                await websocket.send_json({"error": "Invalid JSON"})
                continue

            frame_b64 = payload.get("frame_base64", "")
            if not frame_b64:
                await websocket.send_json({"error": "Missing frame_base64"})
                continue

            try:
                result = await _process_frame(session_id, frame_b64, payload.get("voice", "nova"))
                narration = result.get("narration", "")
                audio_b64 = result.pop("audio_base64", None)
                result.pop("dashboard", None)

                await websocket.send_json(result)

                if narration and audio_b64:
                    await websocket.send_bytes(base64.b64decode(audio_b64))

            except Exception as e:
                await websocket.send_json({"error": str(e), "should_speak": False})

    except WebSocketDisconnect:
        pass
    except Exception as e:
        try:
            await websocket.send_json({"error": str(e)})
            await websocket.close()
        except Exception:
            pass


# ── Camera control: server-side autonomous capture ────────────────────────────

@router.post("/camera/start")
async def start_camera(request: CameraStartRequest):
    """
    Start autonomous camera capture on the server device.
    AI continuously observes through the camera and pushes results
    to all clients subscribed on /stream/ws-camera/{session_id}.
    """
    if camera_service.is_running:
        return {"status": "already_running", "session_id": camera_service.session_id}
    return await camera_service.start(
        session_id=request.session_id,
        on_result=_broadcast,
        camera_index=request.camera_index,
        fps_limit=request.fps_limit,
    )


@router.post("/camera/stop")
async def stop_camera():
    """Stop autonomous camera capture."""
    return await camera_service.stop()


@router.get("/camera/status")
async def camera_status():
    """Check if autonomous camera is running."""
    return {
        "running": camera_service.is_running,
        "session_id": camera_service.session_id if camera_service.is_running else None,
        "fps_limit": camera_service.fps_limit if camera_service.is_running else None,
    }


@router.post("/camera/snap")
async def snap_frame(session_id: str = "default", voice: str = "nova"):
    """Capture one frame from server camera right now and run the full pipeline."""
    frame_b64 = camera_service.capture_frame_b64()
    if not frame_b64:
        raise HTTPException(status_code=503, detail="Camera not accessible. Check device camera_index.")
    try:
        return await _process_frame(session_id, frame_b64, voice)
    except Exception as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.websocket("/ws-camera/{session_id}")
async def websocket_camera_output(websocket: WebSocket, session_id: str):
    """
    Subscribe to autonomous camera narration — no input needed, server pushes.

    1. Start camera: POST /stream/camera/start
    2. Connect here and just listen.

    Server pushes whenever AI decides to speak:
    { "narration": "...", "should_speak": bool, "audio_base64": "<mp3>",
      "priority": int, "winner_agent": "..." }
    """
    await websocket.accept()
    _camera_clients.append(websocket)
    try:
        while True:
            await asyncio.sleep(20)
            try:
                await websocket.send_json({"heartbeat": True})
            except Exception:
                break  # send failed — connection is dead, exit to finally
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        try:
            _camera_clients.remove(websocket)
        except ValueError:
            pass
