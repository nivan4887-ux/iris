import asyncio
import base64
import time
import threading
from typing import Optional, Callable, Awaitable

import cv2


class CameraService:
    """
    Captures frames from the device camera and feeds them into the Aura pipeline.

    Usage:
        await camera_service.start(session_id, on_result)
        await camera_service.stop()

    on_result is called with the pipeline result dict each time the AI has
    something to say (or silence — the callback decides what to do with it).
    """

    def __init__(self):
        self._cap: Optional[cv2.VideoCapture] = None
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self.session_id: str = "default"
        self.camera_index: int = 0
        self.fps_limit: float = 0.5          # Max frames/sec sent to AI (1 per 2s default)
        self.jpeg_quality: int = 85

    # ── Public API ────────────────────────────────────────────────────────────

    async def start(
        self,
        session_id: str = "default",
        on_result: Optional[Callable[[dict], Awaitable[None]]] = None,
        camera_index: int = 0,
        fps_limit: float = 0.5,
    ):
        if self._running:
            return {"status": "already_running"}

        self.session_id = session_id
        self.camera_index = camera_index
        self.fps_limit = fps_limit

        self._cap = cv2.VideoCapture(camera_index)
        if not self._cap.isOpened():
            raise RuntimeError(f"Cannot open camera at index {camera_index}")

        self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
        self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

        self._running = True
        self._task = asyncio.create_task(self._capture_loop(on_result))
        return {"status": "started", "camera_index": camera_index, "fps_limit": fps_limit}

    async def stop(self):
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        if self._cap:
            self._cap.release()
            self._cap = None
        return {"status": "stopped"}

    def capture_frame_b64(self) -> Optional[str]:
        """Capture a single frame right now and return as base64 JPEG string."""
        if not self._cap or not self._cap.isOpened():
            cap = cv2.VideoCapture(self.camera_index)
            ret, frame = cap.read()
            cap.release()
        else:
            ret, frame = self._cap.read()

        if not ret or frame is None:
            return None

        _, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, self.jpeg_quality])
        return base64.b64encode(buf.tobytes()).decode("utf-8")

    @property
    def is_running(self) -> bool:
        return self._running

    # ── Internal capture loop ─────────────────────────────────────────────────

    async def _capture_loop(self, on_result: Optional[Callable[[dict], Awaitable[None]]]):
        from routers.stream import _process_frame

        interval = 1.0 / max(self.fps_limit, 0.1)

        while self._running:
            loop_start = time.time()

            frame_b64 = await asyncio.to_thread(self._read_frame)
            if frame_b64 is None:
                await asyncio.sleep(0.5)
                continue

            try:
                result = await _process_frame(self.session_id, frame_b64)
                if on_result:
                    await on_result(result)
            except Exception as e:
                if on_result:
                    await on_result({"error": str(e), "should_speak": False})

            elapsed = time.time() - loop_start
            wait = max(0.0, interval - elapsed)
            if wait:
                await asyncio.sleep(wait)

    def _read_frame(self) -> Optional[str]:
        if not self._cap or not self._cap.isOpened():
            return None
        ret, frame = self._cap.read()
        if not ret or frame is None:
            return None
        _, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, self.jpeg_quality])
        return base64.b64encode(buf.tobytes()).decode("utf-8")


camera_service = CameraService()
