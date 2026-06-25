"""Speech-to-text — transcribes a voice memo via fal.ai Whisper.

Used for the front of the new pipeline: Mayke records a Portuguese voice memo
explaining an idea his way; this turns it into text for the LLM to adapt.
Reuses the existing FAL_API_KEY (same key as image generation).
"""
import base64
from pathlib import Path

import requests
from django.conf import settings

MODEL_URL = "https://fal.run/fal-ai/whisper"

_MIME = {
    ".mp3": "audio/mpeg",
    ".m4a": "audio/mp4",
    ".mp4": "audio/mp4",
    ".wav": "audio/wav",
    ".ogg": "audio/ogg",
    ".oga": "audio/ogg",
    ".webm": "audio/webm",
    ".flac": "audio/flac",
}


class NotConfigured(Exception):
    pass


def is_configured() -> bool:
    return bool(settings.FAL_API_KEY)


def _data_uri(path: Path) -> str:
    mime = _MIME.get(path.suffix.lower(), "application/octet-stream")
    b64 = base64.b64encode(path.read_bytes()).decode()
    return f"data:{mime};base64,{b64}"


def transcribe(audio_path, language: str = "pt") -> str:
    """Transcribe an audio file. Defaults to Portuguese; returns plain text."""
    if not is_configured():
        raise NotConfigured("Set FAL_API_KEY in your .env (needed for transcription)")

    path = Path(audio_path)
    if not path.exists():
        raise FileNotFoundError(f"Audio file not found: {path}")

    resp = requests.post(
        MODEL_URL,
        headers={
            "Authorization": f"Key {settings.FAL_API_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "audio_url": _data_uri(path),
            "task": "transcribe",
            "language": language,
        },
        timeout=300,
    )
    resp.raise_for_status()
    data = resp.json()
    return (data.get("text") or "").strip()
