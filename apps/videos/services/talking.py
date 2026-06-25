"""Talking-avatar render — avatar still + voiceover → talking MP4 via fal Kling AI Avatar v2.

Replaces the old image-slideshow renderer. The proven pipeline: take the chosen
avatar's portrait + the generated voiceover, send both to fal's Kling AI Avatar
(which animates cartoons/animals/stylized characters, not just human faces), and
save the resulting vertical MP4. Queue endpoint: submit → poll → fetch.
"""
import base64
import time
from pathlib import Path

import requests
from django.conf import settings

QUEUE_URL = "https://queue.fal.run/fal-ai/kling-video/ai-avatar/v2/standard"

# Steer the mouth: talk with small, NORMAL teeth — not oversized, not an empty mouth.
STEER_PROMPT = (
    "A 3d animated character speaking to camera. The mouth opens and closes naturally "
    "to talk, showing small NORMAL-sized teeth — subtle and natural, NOT large, NOT "
    "oversized, NOT exaggerated. Confident delivery."
)


class NotConfigured(Exception):
    pass


def is_configured() -> bool:
    return bool(settings.FAL_API_KEY)


def _data_uri(path: Path, mime: str) -> str:
    return f"data:{mime};base64," + base64.b64encode(path.read_bytes()).decode()


def _media_path(media_url_or_name: str) -> Path:
    """Resolve a /media/... URL or a storage-relative name to an absolute path."""
    rel = media_url_or_name.replace(settings.MEDIA_URL, "", 1)
    return Path(settings.MEDIA_ROOT) / rel


def render_video(video) -> str:
    """Render a talking-avatar MP4 for `video`; return its media URL.

    Needs: video.avatar (with a generated image) + video.voice_url (a voiceover mp3).
    """
    if not is_configured():
        raise NotConfigured("Set FAL_API_KEY in your .env (needed for the talking avatar)")
    if not video.avatar_id or not video.avatar or not video.avatar.image:
        raise NotConfigured("Pick an avatar (with a generated image) for this video first.")
    if not video.voice_url:
        raise NotConfigured("Generate the voiceover first.")

    avatar_img = _media_path(video.avatar.image.name)
    if not avatar_img.exists():
        raise NotConfigured("The avatar has no generated image on disk yet.")
    audio = _media_path(video.voice_url)
    if not audio.exists():
        raise NotConfigured("Voiceover file missing — regenerate the voice.")

    headers = {
        "Authorization": f"Key {settings.FAL_API_KEY}",
        "Content-Type": "application/json",
    }
    submit = requests.post(
        QUEUE_URL,
        headers=headers,
        json={
            "image_url": _data_uri(avatar_img, "image/png"),
            "audio_url": _data_uri(audio, "audio/mpeg"),
            "prompt": STEER_PROMPT,
        },
        timeout=120,
    )
    submit.raise_for_status()
    js = submit.json()
    status_url, response_url = js["status_url"], js["response_url"]

    for _ in range(180):  # ~15 min ceiling
        status = requests.get(status_url, headers=headers, timeout=60).json().get("status")
        if status == "COMPLETED":
            break
        if status in ("FAILED", "ERROR"):
            raise RuntimeError(f"fal avatar render failed: {status}")
        time.sleep(5)
    else:
        raise RuntimeError("fal avatar render timed out")

    res = requests.get(response_url, headers=headers, timeout=120).json()
    out = Path(settings.MEDIA_ROOT) / "videos" / f"video_{video.pk}.mp4"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(requests.get(res["video"]["url"], timeout=300).content)
    return f"{settings.MEDIA_URL}videos/video_{video.pk}.mp4"
