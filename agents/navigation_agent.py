from models.agent_state import AgentState
from models.scene import PriorityLevel


def run_navigation_agent(state: AgentState) -> AgentState:
    scene = state.get("scene_graph") or {}
    path_clear = scene.get("path_clear", True)
    objects = scene.get("objects", [])

    blockers = [o for o in objects if o.get("position") == "ahead" and o.get("distance") == "near"]

    if not path_clear or blockers:
        parts = []
        if not path_clear:
            parts.append("path ahead is blocked")
        if blockers:
            labels = [o.get("label", "obstacle") for o in blockers[:2]]
            parts.append(f"{', '.join(labels)} directly ahead")

        score = 0.75 if not path_clear else 0.55

        state["navigation_result"] = {
            "agent": "navigation",
            "needs_guidance": True,
            "priority": PriorityLevel.NAVIGATION,
            "score": score,
            "message": "; ".join(parts),
        }
    else:
        state["navigation_result"] = {
            "agent": "navigation",
            "needs_guidance": False,
            "priority": PriorityLevel.BACKGROUND,
            "score": 0.0,
            "message": "",
        }

    return state
