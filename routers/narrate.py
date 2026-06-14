from fastapi import APIRouter, Response
from pydantic import BaseModel
from services.narration_service import generate_narration
from services.speech_service import text_to_speech

router = APIRouter(prefix="/narrate", tags=["Narrate"])


class NarrateRequest(BaseModel):
    message: str
    context: str = ""
    return_audio: bool = False
    voice: str = "nova"


@router.post("")
async def narrate(request: NarrateRequest):
    """Generate Aura-style narration from a raw message. Optionally return MP3 audio."""
    narration = await generate_narration(request.message, request.context)

    if request.return_audio:
        audio = await text_to_speech(narration, request.voice)
        return Response(content=audio, media_type="audio/mpeg")

    return {"narration": narration}
