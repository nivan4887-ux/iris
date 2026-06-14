from typing import TypedDict, Optional


class AgentState(TypedDict):
    session_id: str
    frame_base64: str
    scene_graph: Optional[dict]
    hazard_result: Optional[dict]
    navigation_result: Optional[dict]
    social_result: Optional[dict]
    ocr_result: Optional[dict]
    suggestion_result: Optional[dict]
    memory_context: Optional[dict]
    triage_decision: Optional[dict]
    final_narration: Optional[str]
    dashboard_log: list
