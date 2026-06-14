from models.agent_state import AgentState
from models.scene import PriorityLevel

_CRITICAL = {"stairs", "step", "steps", "curb", "vehicle", "car", "truck", "bus", "wet floor", "pole", "cable"}


def run_hazard_agent(state: AgentState) -> AgentState:
    scene = state.get("scene_graph") or {}
    hazards = scene.get("hazards", [])

    if not hazards:
        state["hazard_result"] = {"agent": "hazard", "has_hazard": False, "priority": PriorityLevel.BACKGROUND, "score": 0.0, "message": ""}
        return state

    best, best_score = None, 0.0

    for h in hazards:
        score = 0.5
        label = h.get("label", "").lower()
        distance = h.get("distance", "far")

        if any(kw in label for kw in _CRITICAL):
            score += 0.3
        if distance == "near":
            score += 0.2
        elif distance == "approaching":
            score += 0.15

        if score > best_score:
            best_score = score
            best = h

    position = best.get("position", "ahead")
    label = best.get("label", "obstacle")
    distance = best.get("distance", "")
    msg = f"{label} {position}" + (f", {distance}" if distance else "")

    memory = state.get("memory_context") or {}
    recent_hazards = memory.get("recent_hazards", [])
    if any(label.lower() in h.lower() for h in recent_hazards):
        msg = f"continuing hazard: {msg}"

    state["hazard_result"] = {
        "agent": "hazard",
        "has_hazard": True,
        "priority": PriorityLevel.SAFETY,
        "score": best_score,
        "message": msg,
        "raw": best,
    }
    return state
