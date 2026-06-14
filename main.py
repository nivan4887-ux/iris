import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse

from services.memory_service import memory_service
from routers import stream, analyze, narrate, voice, dashboard


@asynccontextmanager
async def lifespan(app: FastAPI):
    await memory_service.connect()
    yield
    await memory_service.disconnect()


app = FastAPI(
    title="Aura 2.0 — Autonomous Context Intelligence",
    description=(
        "AI companion for visually impaired users. "
        "Continuously observes the environment, triages observations by priority, "
        "suppresses noise, and delivers only what matters."
    ),
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(stream.router)
app.include_router(analyze.router)
app.include_router(narrate.router)
app.include_router(voice.router)
app.include_router(dashboard.router)


@app.get("/", tags=["Root"])
async def root():
    return {
        "name": "Aura 2.0",
        "tagline": "Autonomous Context Intelligence for the Visually Impaired",
        "version": "2.0.0",
        "status": "running",
        "endpoints": {
            "stream_frame": "POST /stream/frame  ← camera frame → AI narration + audio",
            "stream_websocket": "WS  /stream/ws/{session_id}  ← continuous camera (JSON audio)",
            "stream_websocket_binary": "WS  /stream/ws-audio/{session_id}  ← continuous camera (binary MP3)",
            "analyze": "POST /analyze",
            "narrate": "POST /narrate",
            "voice_query": "POST /voice/query",
            "voice_transcribe": "POST /voice/transcribe",
            "voice_query_audio": "POST /voice/query-audio",
            "dashboard_state": "GET  /dashboard/state",
            "dashboard_history": "GET  /dashboard/history",
            "docs": "GET  /docs",
        },
    }


@app.get("/health", tags=["Root"])
async def health():
    return {"status": "healthy"}


@app.get("/ui", tags=["UI"], response_class=FileResponse)
async def serve_ui():
    """Browser dashboard — open this URL in a browser to use Aura 2.0."""
    index_path = os.path.join(os.path.dirname(__file__), "static", "index.html")
    if not os.path.exists(index_path):
        return HTMLResponse("<h1>UI not found</h1><p>static/index.html is missing.</p>", status_code=404)
    return FileResponse(index_path, media_type="text/html")
