from models.agent_state import AgentState
from models.scene import PriorityLevel


def run_social_agent(state: AgentState) -> AgentState:
    scene = state.get("scene_graph") or {}
    people = scene.get("people", [])
    memory = state.get("memory_context") or {}
    previously_seen = memory.get("last_people_count", 0)

    if not people:
        state["social_result"] = {
            "agent": "social",
            "has_social": False,
            "priority": PriorityLevel.BACKGROUND,
            "score": 0.0,
            "message": "",
        }
        return state

    total = sum(p.get("count", 1) for p in people)

    position_groups: dict[str, int] = {}
    for p in people:
        pos = p.get("position", "nearby")
        position_groups[pos] = position_groups.get(pos, 0) + p.get("count", 1)

    # "remains" prefix when the same count was seen in the previous frame
    same_as_before = (previously_seen == total)
    verb = "remains" if same_as_before and total == 1 else "remain" if same_as_before else ""

    if total == 1:
        pos = people[0].get("position", "nearby")
        dist = people[0].get("distance", "")
        base = f"one person {pos}" + (f", {dist}" if dist else "")
        msg = f"that person {verb} {pos}" if verb else base
    elif total <= 3:
        parts = [f"{cnt} {'person' if cnt == 1 else 'people'} {pos}" for pos, cnt in position_groups.items()]
        base = f"{total} people — " + ", ".join(parts)
        msg = f"those {total} people {verb} nearby" if verb else base
    else:
        msg = f"the group of {total} people {verb} nearby" if verb else f"a group of {total} people in the area"

    state["social_result"] = {
        "agent": "social",
        "has_social": True,
        "priority": PriorityLevel.SOCIAL,
        "score": min(0.5 + total * 0.05, 0.8),
        "message": msg,
        "total_people": total,
    }
    return state
