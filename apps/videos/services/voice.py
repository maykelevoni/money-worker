"""Voice cloning + TTS via FAL F5-TTS.

Clones a target voice zero-shot from one short reference clip, then narrates any
script in that voice. Replaces ElevenLabs (which gated cloning behind a paid
membership). The reference clip lives on the Avatar (`voice_ref`); there is no
separate "create voice" step — F5-TTS clones from the sample on every call.
Reuses the existing FAL_API_KEY (same key as images/transcription).
"""
import base64
import mimetypes

import requests
from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage

RUN_URL = "https://fal.run/fal-ai/f5-tts"


class NotConfigured(Exception):
    pass


def is_configured() -> bool:
    return bool(settings.FAL_API_KEY)


def _ref_audio_url(ref_audio) -> str:
    """Something FAL can fetch for the reference clip: its public URL when the file
    has one (e.g. R2), otherwise an inline data URI (works for local files too)."""
    try:
        url = ref_audio.url
        if isinstance(url, str) and url.startswith("http"):
            return url
    except Exception:
        pass
    ref_audio.open("rb")
    try:
        data = ref_audio.read()
    finally:
        ref_audio.close()
    mime = mimetypes.guess_type(getattr(ref_audio, "name", "ref.mp3"))[0] or "audio/mpeg"
    return f"data:{mime};base64," + base64.b64encode(data).decode()


def generate_voiceover(text, filename, ref_audio, ref_text=""):
    """Render `text` to speech in the reference voice, store it (local ↔ R2), and
    return the saved file's URL.

    `ref_audio` is the Avatar.voice_ref file (the cloning sample) — required, since
    F5-TTS needs a reference to clone. `ref_text` is what's spoken in that clip; if
    omitted, FAL transcribes it automatically.
    """
    if not is_configured():
        raise NotConfigured("Set FAL_API_KEY in your .env")
    if not ref_audio:
        raise NotConfigured(
            "No voice reference clip set — add one on the avatar (voice_ref) to clone from."
        )

    payload = {
        "gen_text": text,
        "ref_audio_url": _ref_audio_url(ref_audio),
        "model_type": "F5-TTS",
        "remove_silence": True,
    }
    if ref_text:
        payload["ref_text"] = ref_text

    resp = requests.post(
        RUN_URL,
        headers={
            "Authorization": f"Key {settings.FAL_API_KEY}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=300,
    )
    resp.raise_for_status()
    out = resp.json().get("audio_url") or {}
    audio_url = out.get("url") if isinstance(out, dict) else out
    if not audio_url:
        raise RuntimeError(f"F5-TTS returned no audio (got: {str(resp.text)[:200]})")

    # Pull the rendered audio and persist it through the storage API (local ↔ R2).
    audio_bytes = requests.get(audio_url, timeout=180).content
    saved = default_storage.save(f"voices/{filename}", ContentFile(audio_bytes))
    return default_storage.url(saved)
