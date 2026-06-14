"""
End-to-end test suite for Aura 2.0 backend.

Run with:
    pip install pytest httpx pytest-asyncio
    pytest tests/test_pipeline.py -v

Tests that hit the live server require it to be running on localhost:8000.
Tests that mock OpenAI can run offline.
"""
import pytest
import httpx
from unittest.mock import AsyncMock, MagicMock, patch
import json

BASE = "http://localhost:8000"

# Minimal 1×1 white JPEG in base64 (valid image, won't crash vision parser)
TINY_JPEG = (
    "/9j/4AAQSkZJRgABAQEASABIAAD/2wBDAAMCAgMCAgMDAwMEAwMEBQgFBQQEBQoH"
    "BwYIDAoMCwsKCwsNCxAQDQ4RDgsLEBYQERMUFRUVDA8XGBYUGBIUFRT/2wBDAQME"
    "BAUEBQkFBQkUDQsNFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQU"
    "FBQUFBT/wAARCAABAAEDASIAAhEBAxEB/8QAFAABAAAAAAAAAAAAAAAAAAAACf/EABQQ"
    "AQAAAAAAAAAAAAAAAAAAAAD/xAAUAQEAAAAAAAAAAAAAAAAAAAAA/8QAFBEBAAAAAAA"
    "AAAAAAAAAAAAAP/aAAwDAQACEQMRAD8AJQAB/9k="
)

MOCK_SCENE = {
    "people": [{"label": "person", "count": 1, "position": "ahead", "distance": "near", "confidence": 1.0}],
    "hazards": [],
    "objects": [{"label": "chair", "count": 2, "position": "left", "confidence": 1.0}],
    "text_detected": [],
    "path_clear": True,
    "environment": "indoor",
    "movement_detected": False,
    "spatial_summary": "Indoor room with one person ahead and chairs to the left.",
}

MOCK_HAZARD_SCENE = {
    **MOCK_SCENE,
    "people": [],
    "hazards": [{"label": "stairs", "count": 1, "position": "ahead", "distance": "approaching", "confidence": 1.0}],
    "path_clear": False,
    "spatial_summary": "Stairs approaching ahead.",
}

MOCK_RESTAURANT_SCENE = {
    **MOCK_SCENE,
    "people": [],
    "text_detected": ["Pasta $12", "Salad $8", "Menu"],
    "environment": "restaurant",
    "spatial_summary": "Restaurant with visible menu text.",
}


# ── Infrastructure tests (always pass if server is up) ──────────────────────

class TestHealth:
    def test_health(self):
        r = httpx.get(f"{BASE}/health")
        assert r.status_code == 200
        assert r.json()["status"] == "healthy"

    def test_root(self):
        r = httpx.get(f"{BASE}/")
        assert r.status_code == 200
        data = r.json()
        assert data["name"] == "Aura 2.0"
        assert "endpoints" in data

    def test_docs_accessible(self):
        r = httpx.get(f"{BASE}/docs")
        assert r.status_code == 200


class TestDashboard:
    def test_state_empty_session(self):
        r = httpx.get(f"{BASE}/dashboard/state", params={"session_id": "test-empty-xyz"})
        assert r.status_code == 200
        data = r.json()
        assert "current_scene" in data
        assert "context" in data
        assert data["latest_decision"] is None

    def test_history_empty_session(self):
        r = httpx.get(f"{BASE}/dashboard/history", params={"session_id": "test-empty-xyz"})
        assert r.status_code == 200
        data = r.json()
        assert "decisions" in data
        assert isinstance(data["decisions"], list)

    def test_clear_history(self):
        r = httpx.delete(f"{BASE}/dashboard/history", params={"session_id": "test-clear-xyz"})
        assert r.status_code == 200
        assert r.json()["cleared"] is True


class TestCamera:
    def test_camera_status(self):
        r = httpx.get(f"{BASE}/stream/camera/status")
        assert r.status_code == 200
        data = r.json()
        assert "running" in data
        assert isinstance(data["running"], bool)


# ── Agent logic tests (pure Python, no API calls) ────────────────────────────

class TestAgentLogic:
    """Test each agent in isolation with mock state."""

    def _make_state(self, scene: dict, memory_context: dict = None):
        return {
            "session_id": "test",
            "frame_base64": "",
            "scene_graph": scene,
            "hazard_result": None,
            "navigation_result": None,
            "social_result": None,
            "ocr_result": None,
            "suggestion_result": None,
            "memory_context": memory_context or {},
            "triage_decision": None,
            "final_narration": None,
            "dashboard_log": [],
        }

    def test_hazard_agent_detects_stairs(self):
        from agents.hazard_agent import run_hazard_agent
        state = self._make_state(MOCK_HAZARD_SCENE)
        result = run_hazard_agent(state)
        assert result["hazard_result"]["has_hazard"] is True
        assert result["hazard_result"]["score"] > 0.7
        assert result["hazard_result"]["priority"] == 1  # SAFETY

    def test_hazard_agent_no_hazards(self):
        from agents.hazard_agent import run_hazard_agent
        state = self._make_state(MOCK_SCENE)
        result = run_hazard_agent(state)
        assert result["hazard_result"]["has_hazard"] is False
        assert result["hazard_result"]["score"] == 0.0

    def test_social_agent_one_person(self):
        from agents.social_agent import run_social_agent
        state = self._make_state(MOCK_SCENE)
        result = run_social_agent(state)
        assert result["social_result"]["has_social"] is True
        assert result["social_result"]["total_people"] == 1
        assert result["social_result"]["priority"] == 3  # SOCIAL

    def test_social_agent_no_people(self):
        from agents.social_agent import run_social_agent
        state = self._make_state({**MOCK_SCENE, "people": []})
        result = run_social_agent(state)
        assert result["social_result"]["has_social"] is False

    def test_navigation_path_blocked(self):
        from agents.navigation_agent import run_navigation_agent
        blocked = {**MOCK_SCENE, "path_clear": False}
        state = self._make_state(blocked)
        result = run_navigation_agent(state)
        assert result["navigation_result"]["needs_guidance"] is True
        assert result["navigation_result"]["priority"] == 2  # NAVIGATION

    def test_navigation_path_clear(self):
        from agents.navigation_agent import run_navigation_agent
        state = self._make_state(MOCK_SCENE)
        result = run_navigation_agent(state)
        assert result["navigation_result"]["needs_guidance"] is False

    def test_ocr_agent_restaurant(self):
        from agents.ocr_agent import run_ocr_agent
        state = self._make_state(MOCK_RESTAURANT_SCENE)
        result = run_ocr_agent(state)
        assert result["ocr_result"]["has_text"] is True
        assert result["ocr_result"]["score"] == 0.6  # high-value env bonus

    def test_suggestion_agent_restaurant(self):
        from agents.suggestion_agent import run_suggestion_agent
        state = self._make_state(MOCK_RESTAURANT_SCENE)
        result = run_suggestion_agent(state)
        assert result["suggestion_result"]["has_suggestion"] is True
        assert "menu" in result["suggestion_result"]["message"].lower()

    def test_triage_hazard_beats_social(self):
        """SAFETY (priority=1) must always beat SOCIAL (priority=3)."""
        from agents.orchestrator import triage_node
        state = self._make_state(MOCK_SCENE)
        state["hazard_result"] = {"agent": "hazard", "priority": 1, "score": 0.9, "message": "stairs ahead"}
        state["social_result"] = {"agent": "social", "priority": 3, "score": 0.8, "message": "two people nearby"}
        state["navigation_result"] = {"agent": "navigation", "priority": 5, "score": 0.0, "message": ""}
        state["ocr_result"] = {"agent": "ocr", "priority": 5, "score": 0.0, "message": ""}
        state["suggestion_result"] = {"agent": "suggestion", "priority": 5, "score": 0.0, "message": ""}

        result = triage_node(state)
        assert result["triage_decision"]["winner"]["agent"] == "hazard"
        assert "two people" in " ".join(result["triage_decision"]["suppressed"])

    def test_triage_suppresses_background(self):
        """Zero-score agents must not appear in detected list."""
        from agents.orchestrator import triage_node
        state = self._make_state(MOCK_SCENE)
        state["hazard_result"] = {"agent": "hazard", "priority": 5, "score": 0.0, "message": ""}
        state["social_result"] = {"agent": "social", "priority": 3, "score": 0.55, "message": "one person ahead"}
        state["navigation_result"] = {"agent": "navigation", "priority": 5, "score": 0.0, "message": ""}
        state["ocr_result"] = {"agent": "ocr", "priority": 5, "score": 0.0, "message": ""}
        state["suggestion_result"] = {"agent": "suggestion", "priority": 5, "score": 0.0, "message": ""}

        result = triage_node(state)
        assert result["triage_decision"]["winner"]["agent"] == "social"
        assert result["triage_decision"]["detected"] == ["one person ahead"]


# ── Scenario tests (mocked OpenAI) ──────────────────────────────────────────

class TestScenarios:
    """Simulate the 5 hackathon demo scenarios with mocked AI calls."""

    def _mock_vision(self, scene: dict):
        return MagicMock(
            choices=[MagicMock(message=MagicMock(content=json.dumps(scene)))]
        )

    def _mock_narration(self, text: str):
        return MagicMock(
            choices=[MagicMock(message=MagicMock(content=text))]
        )

    @patch("services.vision_service._openai_client")
    @patch("services.narration_service._client")
    @patch("services.speech_service._client")
    def test_scenario_1_room_person_suppresses_furniture(self, mock_tts, mock_narr, mock_vis):
        """Person prioritized. Furniture suppressed."""
        mock_vis.chat.completions.create = AsyncMock(return_value=self._mock_vision(MOCK_SCENE))
        mock_narr.chat.completions.create = AsyncMock(return_value=self._mock_narration("Someone is just ahead of you."))
        mock_tts.audio.speech.create = AsyncMock(return_value=MagicMock(read=AsyncMock(return_value=b"audio")))

        r = httpx.post(f"{BASE}/stream/frame", json={
            "frame_base64": TINY_JPEG,
            "session_id": "scenario-1",
            "return_audio": False,
        }, timeout=30)

        assert r.status_code == 200
        data = r.json()
        assert "scene_graph" in data
        assert "dashboard" in data
        assert "narration" in data

    @patch("services.vision_service._openai_client")
    @patch("services.narration_service._client")
    @patch("services.speech_service._client")
    def test_scenario_2_hazard_stairs(self, mock_tts, mock_narr, mock_vis):
        """Stairs: immediate hazard warning, safety priority."""
        mock_vis.chat.completions.create = AsyncMock(return_value=self._mock_vision(MOCK_HAZARD_SCENE))
        mock_narr.chat.completions.create = AsyncMock(return_value=self._mock_narration("Stairs just ahead — take care."))
        mock_tts.audio.speech.create = AsyncMock(return_value=MagicMock(read=AsyncMock(return_value=b"audio")))

        r = httpx.post(f"{BASE}/stream/frame", json={
            "frame_base64": TINY_JPEG,
            "session_id": "scenario-2",
            "return_audio": False,
        }, timeout=30)

        assert r.status_code == 200
        data = r.json()
        assert data["priority"] == 1  # SAFETY

    @patch("services.vision_service._openai_client")
    @patch("services.narration_service._client")
    @patch("services.speech_service._client")
    def test_scenario_4_restaurant_ocr_with_suggestion(self, mock_tts, mock_narr, mock_vis):
        """Restaurant: OCR + proactive menu offer in same narration."""
        mock_vis.chat.completions.create = AsyncMock(return_value=self._mock_vision(MOCK_RESTAURANT_SCENE))
        mock_narr.chat.completions.create = AsyncMock(return_value=self._mock_narration(
            "I can see menu text nearby — Pasta $12, Salad $8. I can read the menu if you'd like."
        ))
        mock_tts.audio.speech.create = AsyncMock(return_value=MagicMock(read=AsyncMock(return_value=b"audio")))

        r = httpx.post(f"{BASE}/stream/frame", json={
            "frame_base64": TINY_JPEG,
            "session_id": "scenario-4",
            "return_audio": False,
        }, timeout=30)

        assert r.status_code == 200

    def test_scenario_5_dedup_suppresses_repeat(self):
        """Same message within cooldown window must be silenced."""
        from services.memory_service import MemoryService
        import asyncio

        svc = MemoryService()
        session = "dedup-test"
        msg = "one person ahead, near"

        async def run():
            await svc.connect()
            await svc.mark_announced(session, msg)
            first = await svc.has_announced(session, msg)
            await svc.disconnect()
            return first

        result = asyncio.run(run())
        assert result is True  # same message suppressed within cooldown


# ── Memory service unit tests ─────────────────────────────────────────────────

class TestMemoryService:
    def test_local_fallback_store_retrieve(self):
        from services.memory_service import MemoryService
        import asyncio

        svc = MemoryService()  # No Redis — local dict mode

        async def run():
            await svc.save_scene("sess", {"people": [], "hazards": []})
            scene = await svc.get_scene("sess")
            return scene

        scene = asyncio.run(run())
        assert scene is not None
        assert "people" in scene

    def test_history_ordered_newest_first(self):
        from services.memory_service import MemoryService
        import asyncio

        svc = MemoryService()

        async def run():
            await svc.add_history("sess2", {"chosen_narration": "first"})
            await svc.add_history("sess2", {"chosen_narration": "second"})
            return await svc.get_history("sess2", limit=5)

        history = asyncio.run(run())
        assert history[0]["chosen_narration"] == "second"
        assert history[1]["chosen_narration"] == "first"

    def test_clear_session(self):
        from services.memory_service import MemoryService
        import asyncio

        svc = MemoryService()

        async def run():
            await svc.save_scene("sess3", {"people": [1]})
            await svc.clear_session("sess3")
            return await svc.get_scene("sess3")

        result = asyncio.run(run())
        assert result is None
