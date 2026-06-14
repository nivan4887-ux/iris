from services.memory_service import memory_service


class ContextService:
    """
    Builds a rich context dict before agents run.
    Replaces the raw memory_context with a structured snapshot that every
    agent can consume without knowing about Redis or session management.

    Output shape (becomes AgentState["memory_context"]):
    {
        "last_people_count":  int,       # previous frame people count
        "recent_hazards":     list[str], # hazard messages from last 5 decisions
        "narration_history":  list[str], # last 5 spoken narrations
        "scene_changed":      bool,      # did scene differ from previous frame?
        "environment":        str,       # current environment label
        "movement_detected":  bool,
    }
    """

    async def build(self, session_id: str, scene_graph: dict) -> dict:
        history = await memory_service.get_history(session_id, limit=10)
        user_context = await memory_service.get_context(session_id)
        prev_scene = await memory_service.get_scene(session_id)

        # ── Narration history ──────────────────────────────────────────────
        narration_history = [
            h["chosen_narration"]
            for h in history
            if h.get("chosen_narration")
        ]

        # ── Recent hazards from decision log ──────────────────────────────
        recent_hazards: list[str] = []
        for h in history[:5]:
            for d in h.get("agent_decisions", []):
                if d.get("agent") == "hazard" and not d.get("suppressed") and d.get("message"):
                    recent_hazards.append(d["message"])

        # ── Scene change detection ─────────────────────────────────────────
        scene_changed = True
        if prev_scene:
            same_people = len(prev_scene.get("people", [])) == len(scene_graph.get("people", []))
            same_hazards = len(prev_scene.get("hazards", [])) == len(scene_graph.get("hazards", []))
            same_env = prev_scene.get("environment") == scene_graph.get("environment")
            scene_changed = not (same_people and same_hazards and same_env)

        return {
            "last_people_count": user_context.get("last_people_count", 0),
            "recent_hazards": recent_hazards[:3],
            "narration_history": narration_history[:5],
            "scene_changed": scene_changed,
            "environment": scene_graph.get("environment", ""),
            "movement_detected": scene_graph.get("movement_detected", False),
        }


context_service = ContextService()
