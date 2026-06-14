from fastapi import APIRouter, UploadFile, File, Response, HTTPException
from pydantic import BaseModel
from services.narration_service import answer_voice_query
from services.speech_service import text_to_speech, transcribe_audio
from services.memory_service import memory_service

router = APIRouter(prefix="/voice", tags=["Voice"])


class VoiceQueryRequest(BaseModel):
    query: str
    session_id: str = "default"
    return_audio: bool = False
    voice: str = "nova"


@router.post("/query")
async def voice_query(request: VoiceQueryRequest):
    """Answer a text query from the user using scene memory and history."""
    scene = await memory_service.get_scene(request.session_id) or {}
    history = await memory_service.get_history(request.session_id, limit=5)

    response_text = await answer_voice_query(request.query, scene, history)

    if request.return_audio:
        audio = await text_to_speech(response_text, request.voice)
        return Response(content=audio, media_type="audio/mpeg")

    return {"response": response_text, "query": request.query}


@router.post("/transcribe")
async def transcribe(file: UploadFile = File(...)):
    """Transcribe an audio file to text using Whisper (for voice-triggered queries)."""
    if not file.content_type or not file.content_type.startswith("audio/"):
        raise HTTPException(status_code=400, detail="File must be an audio type")

    audio_bytes = await file.read()
    text = await transcribe_audio(audio_bytes, file.filename or "audio.webm", file.content_type)
    return {"text": text}


@router.post("/query-audio")
async def voice_query_from_audio(
    file: UploadFile = File(...),
    session_id: str = "default",
    return_audio: bool = False,
    voice: str = "nova",
):
    """Full pipeline: audio in → Whisper → GPT-4o → (TTS out or text out)."""
    audio_bytes = await file.read()
    query = await transcribe_audio(audio_bytes, file.filename or "audio.webm", file.content_type or "audio/webm")

    scene = await memory_service.get_scene(session_id) or {}
    history = await memory_service.get_history(session_id, limit=5)
    response_text = await answer_voice_query(query, scene, history)

    if return_audio:
        audio = await text_to_speech(response_text, voice)
        return Response(content=audio, media_type="audio/mpeg")

    return {"query": query, "response": response_text}
