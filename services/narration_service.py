from openai import AsyncOpenAI
from config import settings

_client = AsyncOpenAI(api_key=settings.openai_api_key)

_MOCK_NARRATIONS = {
    "hazard": "Careful — there are stairs directly ahead of you.",
    "navigation": "Your path is blocked. Try stepping to the right.",
    "social": "Someone is standing just ahead of you.",
    "ocr": "I can see text nearby. There's a menu with Pasta for twelve dollars.",
    "suggestion": "Would you like me to read the full menu for you?",
}

async def _mock_narration(priority_message: str) -> str:
    for key, text in _MOCK_NARRATIONS.items():
        if key in priority_message.lower():
            return text
    return f"I noticed: {priority_message}."

_SYSTEM = """You are Aura, a calm and precise AI guide for visually impaired users.
Rules:
- Maximum 2 short sentences per response
- Use natural spoken language — never robotic phrasing like "object detected"
- Lead with the most safety-critical information
- Use directional cues: ahead, to your left, to your right, behind you
- For hazards: be clear and direct without causing panic
- For social: use natural grouping (e.g. "a small group", "someone")
- Never say "I detected", "I see", or "image shows"
- Speak as if gently guiding a trusted friend"""


async def generate_narration(priority_message: str, context: str = "") -> str:
    if settings.mock_mode:
        return await _mock_narration(priority_message)

    user_content = priority_message
    if context:
        user_content = f"Scene context: {context}\nNarrate: {priority_message}"

    response = await _client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": _SYSTEM},
            {"role": "user", "content": user_content},
        ],
        max_tokens=100,
        temperature=0.4,
    )
    return response.choices[0].message.content.strip()


async def answer_voice_query(query: str, scene: dict, history: list[dict]) -> str:
    parts = []

    if scene:
        parts.append(f"Current scene: {scene.get('spatial_summary', 'unclear')}")

    if history:
        recent_narrations = [h.get("chosen_narration", "") for h in history[:3] if h.get("chosen_narration")]
        if recent_narrations:
            parts.append("Recent narrations: " + "; ".join(recent_narrations))

    parts.append(f"User asks: {query}")

    response = await _client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": _SYSTEM},
            {"role": "user", "content": "\n".join(parts)},
        ],
        max_tokens=150,
        temperature=0.4,
    )
    return response.choices[0].message.content.strip()
