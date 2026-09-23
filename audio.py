"""On-demand audio; never writes shared files or stores credentials globally."""

import hashlib
import os

from openai import OpenAI

from models import STYLES


def audio_key(text: str, style: str, voice: str) -> str:
    return hashlib.sha256(f"{style}:{voice}:{text}".encode()).hexdigest()


def synthesize(api_key: str, text: str, style: str, voice: str = "nova") -> bytes:
    if not text.strip() or len(text) > 4000:
        raise ValueError("Audio needs a non-empty passage of at most 4,000 characters.")
    if voice not in {"nova", "coral", "alloy"} or style not in STYLES:
        raise ValueError("Choose a supported voice and storytelling style.")
    with OpenAI(api_key=api_key, timeout=60, max_retries=2) as client:
        response = client.audio.speech.create(
            model=os.getenv("TOUR_TTS_MODEL", "gpt-4o-mini-tts"),
            voice=voice,
            input=text,
            instructions=STYLES[style] + " Speak naturally, with brief pauses.",
            response_format="mp3",
        )
        return response.content


def transcribe(api_key: str, data: bytes) -> str:
    if not data or len(data) > 10_000_000:
        raise ValueError("Record a short question under 10 MB.")
    with OpenAI(api_key=api_key, timeout=60, max_retries=2) as client:
        result = client.audio.transcriptions.create(
            model=os.getenv("TOUR_TRANSCRIPTION_MODEL", "gpt-4o-mini-transcribe"),
            file=("question.wav", data, "audio/wav"),
        )
        return result.text
