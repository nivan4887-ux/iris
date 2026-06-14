import json
import re
from openai import AsyncOpenAI
from config import settings
from models.scene import SceneGraph

_openai_client = AsyncOpenAI(api_key=settings.openai_api_key)

SCENE_ANALYSIS_PROMPT = """Analyze this image for a blind user's AI navigation assistant. Return a JSON object with EXACTLY this structure — no other text:

{
  "people": [
    {"label": "person description", "count": 1, "position": "left|right|ahead|behind", "distance": "near|far|approaching"}
  ],
  "hazards": [
    {"label": "hazard name", "count": 1, "position": "left|right|ahead|behind", "distance": "near|far|approaching"}
  ],
  "objects": [
    {"label": "object name", "count": 1, "position": "left|right|ahead|behind"}
  ],
  "text_detected": ["visible text strings"],
  "path_clear": true,
  "environment": "indoor|outdoor|restaurant|street|office|home|other",
  "movement_detected": false,
  "spatial_summary": "one sentence overview of the space"
}

Rules:
- Hazards include: stairs, steps, curbs, vehicles, wet floors, low ceilings, sharp objects, open doors, poles, cables
- near = within 2 metres, far = beyond 2 metres, approaching = moving toward the camera
- Only include objects that matter for safe navigation (ignore decorations, paintings, etc.)
- Positions: left, right, ahead, behind — always relative to the camera direction
- Return ONLY the JSON object, no markdown fences, no explanation"""


async def analyze_frame(frame_base64: str) -> SceneGraph:
    response = await _openai_client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{frame_base64}",
                            "detail": "high",
                        },
                    },
                    {"type": "text", "text": SCENE_ANALYSIS_PROMPT},
                ],
            }
        ],
        max_tokens=800,
        temperature=0.1,
    )

    content = response.choices[0].message.content.strip()
    content = re.sub(r"^```(?:json)?\s*", "", content)
    content = re.sub(r"\s*```$", "", content)

    data = json.loads(content)
    return SceneGraph(**data)


async def analyze_frame_gemini(frame_base64: str) -> SceneGraph:
    import asyncio
    import base64
    import google.generativeai as genai

    genai.configure(api_key=settings.gemini_api_key)
    model = genai.GenerativeModel("gemini-1.5-pro-vision")

    image_bytes = base64.b64decode(frame_base64)
    image_part = {"mime_type": "image/jpeg", "data": image_bytes}

    # Gemini SDK is sync — run in thread to avoid blocking the event loop
    response = await asyncio.to_thread(model.generate_content, [SCENE_ANALYSIS_PROMPT, image_part])
    content = response.text.strip()
    content = re.sub(r"^```(?:json)?\s*", "", content)
    content = re.sub(r"\s*```$", "", content)

    data = json.loads(content)
    return SceneGraph(**data)


_MOCK_SCENES = [
    {
        "people": [{"label": "person", "count": 1, "position": "ahead", "distance": "near", "confidence": 1.0}],
        "hazards": [], "objects": [{"label": "chair", "count": 2, "position": "left", "confidence": 0.9}],
        "text_detected": [], "path_clear": True, "environment": "indoor",
        "movement_detected": False, "spatial_summary": "Indoor room with one person standing just ahead of you.",
    },
    {
        "people": [], "hazards": [{"label": "stairs", "count": 1, "position": "ahead", "distance": "approaching", "confidence": 1.0}],
        "objects": [], "text_detected": [], "path_clear": False, "environment": "indoor",
        "movement_detected": False, "spatial_summary": "Staircase directly ahead — use caution.",
    },
    {
        "people": [{"label": "person", "count": 2, "position": "left", "distance": "near", "confidence": 0.9}],
        "hazards": [], "objects": [], "text_detected": ["Menu", "Pasta $12", "Salad $8"],
        "path_clear": True, "environment": "restaurant",
        "movement_detected": False, "spatial_summary": "Restaurant setting with two people to your left and menu text visible.",
    },
]
_mock_idx = 0
_mock_frame_count = 0
_FRAMES_PER_SCENE = 8  # hold each scene for ~16 seconds before switching


async def get_scene(frame_base64: str) -> SceneGraph:
    if settings.mock_mode:
        global _mock_idx, _mock_frame_count
        data = _MOCK_SCENES[_mock_idx % len(_MOCK_SCENES)]
        _mock_frame_count += 1
        if _mock_frame_count >= _FRAMES_PER_SCENE:
            _mock_idx += 1
            _mock_frame_count = 0
        return SceneGraph(**data)
    if settings.vision_provider == "gemini" and settings.gemini_api_key:
        return await analyze_frame_gemini(frame_base64)
    return await analyze_frame(frame_base64)
