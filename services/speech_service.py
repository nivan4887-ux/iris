from openai import AsyncOpenAI
from config import settings
from typing import Literal

_client = AsyncOpenAI(api_key=settings.openai_api_key)

VoiceOption = Literal["alloy", "echo", "fable", "onyx", "nova", "shimmer"]


_SILENT_MP3 = bytes([
    0xFF, 0xFB, 0x90, 0x00, 0x00, 0x00, 0x00, 0x00,
    0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
])


async def text_to_speech(text: str, voice: VoiceOption = "nova") -> bytes:
    if settings.mock_mode:
        return _SILENT_MP3  # silent frame — no API call needed
    response = await _client.audio.speech.create(
        model="tts-1",
        voice=voice,
        input=text,
    )
    return await response.read()


async def transcribe_audio(audio_bytes: bytes, filename: str = "audio.webm", mime_type: str = "audio/webm") -> str:
    transcript = await _client.audio.transcriptions.create(
        model="whisper-1",
        file=(filename, audio_bytes, mime_type),
    )
    return transcript.text
