from pydantic import BaseModel
from typing import Optional


class AgentDecision(BaseModel):
    agent: str
    priority: int
    score: float
    message: str
    suppressed: bool = False
    reason: str = ""


class NarrationDecision(BaseModel):
    session_id: str
    timestamp: float
    detected_elements: list[str]
    suppressed_elements: list[str]
    chosen_narration: str
    priority_level: int
    reasoning: str
    agent_decisions: list[AgentDecision] = []


class NarrationResponse(BaseModel):
    narration: str
    priority: int
    should_speak: bool
    dashboard: Optional[NarrationDecision] = None
