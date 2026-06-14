from models.agent_state import AgentState
from models.scene import PriorityLevel

_SUGGESTIONS = {
    "restaurant": "I can read the menu if you'd like.",
    "office": "I can help you read any documents or signage nearby.",
    "street": "I can help identify buses, street signs, or storefronts.",
    "outdoor": "I can describe the surroundings or identify landmarks ahead.",
    "home": "Let me know if you'd like me to read anything.",
}


def run_suggestion_agent(state: AgentState) -> AgentState:
    scene = state.get("scene_graph") or {}
    environment = scene.get("environment", "")
    texts = scene.get("text_detected", [])

    suggestion = _SUGGESTIONS.get(environment, "")

    if not suggestion and texts:
        suggestion = "There's some text nearby — would you like me to read it?"

    if suggestion:
        state["suggestion_result"] = {
            "agent": "suggestion",
            "has_suggestion": True,
            "priority": PriorityLevel.INFORMATIONAL,
            "score": 0.35,
            "message": suggestion,
        }
    else:
        state["suggestion_result"] = {
            "agent": "suggestion",
            "has_suggestion": False,
            "priority": PriorityLevel.BACKGROUND,
            "score": 0.0,
            "message": "",
        }
    return state
