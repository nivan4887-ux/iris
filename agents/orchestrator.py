from langgraph.graph import StateGraph, END
from models.agent_state import AgentState
from agents.hazard_agent import run_hazard_agent
from agents.navigation_agent import run_navigation_agent
from agents.social_agent import run_social_agent
from agents.ocr_agent import run_ocr_agent
from agents.suggestion_agent import run_suggestion_agent
from services.narration_service import generate_narration
from services.memory_service import memory_service
from services.context_service import context_service


# ── Triage node ───────────────────────────────────────────────────────────────

def triage_node(state: AgentState) -> AgentState:
    """Rank all agent results by priority + score and select the winner."""
    all_results = [
        state.get("hazard_result") or {},
        state.get("navigation_result") or {},
        state.get("social_result") or {},
        state.get("ocr_result") or {},
        state.get("suggestion_result") or {},
    ]

    active = [r for r in all_results if r.get("score", 0) > 0 and r.get("message")]
    active.sort(key=lambda r: (r.get("priority", 5), -r.get("score", 0)))

    detected = [r.get("message", "") for r in active]
    winner = active[0] if active else None
    suppressed = [r.get("message", "") for r in active[1:]] if winner else detected

    state["triage_decision"] = {
        "winner": winner,
        "detected": detected,
        "suppressed": suppressed,
    }
    return state


# ── Narration node (async) ────────────────────────────────────────────────────

async def narration_node(state: AgentState) -> AgentState:
    """Generate the final spoken narration for the winning agent result."""
    triage = state.get("triage_decision") or {}
    winner = triage.get("winner")
    session_id = state.get("session_id", "default")

    # Always update people count so context_service has fresh data next frame,
    # regardless of whether narration is suppressed by dedup or no-winner.
    social = state.get("social_result") or {}
    await memory_service.update_context(session_id, {
        "last_people_count": social.get("total_people", 0) if social.get("has_social") else 0
    })

    if not winner or not winner.get("message"):
        state["final_narration"] = ""
        return state

    message = winner["message"]

    # Use the base message (strip "continuing hazard:" prefix) as the dedup key
    # so repeated frames of the same hazard don't bypass cooldown.
    dedup_key = message.removeprefix("continuing hazard: ")

    if await memory_service.has_announced(session_id, dedup_key):
        state["final_narration"] = ""
        return state

    # If winner is OCR and a suggestion exists, append it so the proactive
    # offer is always heard when text is detected (fixes suppression bug).
    suggestion_result = state.get("suggestion_result") or {}
    suggestion_msg = suggestion_result.get("message", "")
    if winner.get("agent") == "ocr" and suggestion_msg:
        message = f"{message}. {suggestion_msg}"

    scene = state.get("scene_graph") or {}
    context = scene.get("spatial_summary", "")
    narration = await generate_narration(message, context)

    await memory_service.mark_announced(session_id, dedup_key)
    state["final_narration"] = narration
    return state


# ── Graph assembly ────────────────────────────────────────────────────────────

def _build_graph() -> object:
    g = StateGraph(AgentState)

    g.add_node("hazard", run_hazard_agent)
    g.add_node("navigation", run_navigation_agent)
    g.add_node("social", run_social_agent)
    g.add_node("ocr", run_ocr_agent)
    g.add_node("suggestion", run_suggestion_agent)
    g.add_node("triage", triage_node)
    g.add_node("narration", narration_node)

    # Sequential pipeline: each agent feeds into the next
    g.set_entry_point("hazard")
    g.add_edge("hazard", "navigation")
    g.add_edge("navigation", "social")
    g.add_edge("social", "ocr")
    g.add_edge("ocr", "suggestion")
    g.add_edge("suggestion", "triage")
    g.add_edge("triage", "narration")
    g.add_edge("narration", END)

    return g.compile()


aura_graph = _build_graph()


# ── Public entry point ────────────────────────────────────────────────────────

async def run_pipeline(session_id: str, frame_base64: str, scene_graph: dict) -> AgentState:
    memory_context = await context_service.build(session_id, scene_graph)

    initial: AgentState = {
        "session_id": session_id,
        "frame_base64": frame_base64,
        "scene_graph": scene_graph,
        "hazard_result": None,
        "navigation_result": None,
        "social_result": None,
        "ocr_result": None,
        "suggestion_result": None,
        "memory_context": memory_context,
        "triage_decision": None,
        "final_narration": None,
        "dashboard_log": [],
    }

    return await aura_graph.ainvoke(initial)
