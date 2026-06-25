"""ElevenLabs client — turns the script into an MP3 voiceover.

Also supports instant voice cloning: clone Mayke's voice once from a few audio
samples, then narrate every video in his own voice. `eleven_multilingual_v2`
clones cross-lingually, so Portuguese samples produce English narration.
"""
from pathlib import Path

import requests
from django.conf import settings

API_BASE = "https://api.elevenlabs.io/v1/text-to-speech"
CLONE_URL = "https://api.elevenlabs.io/v1/voices/add"
DEFAULT_VOICE = "21m00Tcm4TlvDq8ikWAM"  # ElevenLabs 'Rachel' — a safe default


class NotConfigured(Exception):
    pass


def clone_voice(name: str, sample_paths: list) -> str:
    """Create an instant-clone voice from local audio samples; return its voice_id.

    Put the returned id in ELEVENLABS_VOICE_ID (.env) to narrate in this voice.
    """
    if not is_configured():
        raise NotConfigured("Set ELEVENLABS_API_KEY in your .env")
    files = []
    handles = []
    try:
        for p in sample_paths:
            path = Path(p)
            if not path.exists():
                raise FileNotFoundError(f"Sample not found: {path}")
            fh = path.open("rb")
            handles.append(fh)
            files.append(("files", (path.name, fh, "audio/mpeg")))
        resp = requests.post(
            CLONE_URL,
            headers={"xi-api-key": settings.ELEVENLABS_API_KEY},
            data={
                "name": name,
                "description": "Mayke — money-worker faceless channel narrator",
            },
            files=files,
            timeout=180,
        )
        resp.raise_for_status()
        return resp.json()["voice_id"]
    finally:
        for fh in handles:
            fh.close()


def is_configured() -> bool:
    return bool(settings.ELEVENLABS_API_KEY)


def generate_voiceover(text: str, filename: str) -> str:
    """Render `text` to an MP3 under MEDIA_ROOT/voices, return the media URL path."""
    if not is_configured():
        raise NotConfigured("Set ELEVENLABS_API_KEY in your .env")

    voice_id = settings.ELEVENLABS_VOICE_ID or DEFAULT_VOICE
    resp = requests.post(
        f"{API_BASE}/{voice_id}",
        headers={
            "xi-api-key": settings.ELEVENLABS_API_KEY,
            "Content-Type": "application/json",
            "Accept": "audio/mpeg",
        },
        json={
            "text": text,
            "model_id": "eleven_multilingual_v2",
            "voice_settings": {"stability": 0.5, "similarity_boost": 0.75},
        },
        timeout=120,
    )
    resp.raise_for_status()

    out_dir = Path(settings.MEDIA_ROOT) / "voices"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / filename
    out_path.write_bytes(resp.content)

    return f"{settings.MEDIA_URL}voices/{filename}"
