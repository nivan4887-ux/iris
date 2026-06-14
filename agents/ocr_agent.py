from models.agent_state import AgentState
from models.scene import PriorityLevel

_HIGH_VALUE_ENVIRONMENTS = {"restaurant", "office", "street"}


def run_ocr_agent(state: AgentState) -> AgentState:
    scene = state.get("scene_graph") or {}
    texts = scene.get("text_detected", [])
    environment = scene.get("environment", "")

    if not texts:
        state["ocr_result"] = {
            "agent": "ocr",
            "has_text": False,
            "priority": PriorityLevel.BACKGROUND,
            "score": 0.0,
            "message": "",
        }
        return state

    score = 0.45
    if environment in _HIGH_VALUE_ENVIRONMENTS:
        score = 0.6

    combined = "; ".join(texts[:3])
    msg = f"text visible: {combined}"

    state["ocr_result"] = {
        "agent": "ocr",
        "has_text": True,
        "priority": PriorityLevel.INFORMATIONAL,
        "score": score,
        "message": msg,
        "texts": texts,
    }
    return state
