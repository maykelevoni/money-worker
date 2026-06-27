"""Upload-Post client — publishes a rendered video to YouTube / TikTok /
Instagram through one unified API, so we don't fight each platform's native
posting API (TikTok app audits, the Instagram/Facebook review, YouTube quota).

Docs: https://docs.upload-post.com/api/upload-video/
"""
from pathlib import Path

import requests
from django.conf import settings

UPLOAD_URL = "https://api.upload-post.com/api/upload"
STATUS_URL = "https://api.upload-post.com/api/uploadposts/status"

# The platforms we expose in the UI today.
PLATFORMS = ["youtube", "tiktok", "instagram"]
PLATFORM_LABELS = {"youtube": "YouTube", "tiktok": "TikTok", "instagram": "Instagram"}


class NotConfigured(Exception):
    pass


def is_configured() -> bool:
    return bool(settings.UPLOAD_POST_API_KEY and settings.UPLOAD_POST_USER)


def _headers() -> dict:
    return {"Authorization": f"Apikey {settings.UPLOAD_POST_API_KEY}"}


def upload_video(file_path, platforms, title, caption="", *, idempotency_key=""):
    """Post a local video file to `platforms`; return the API's JSON response.

    `title` is required by YouTube; `caption` becomes the description/body where
    each platform supports it. Uploads run async so the request returns quickly
    with a `request_id` to poll via `check_status`.
    """
    if not is_configured():
        raise NotConfigured("Set UPLOAD_POST_API_KEY and UPLOAD_POST_USER in your .env")
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Video file not found: {path}")

    data = [
        ("user", settings.UPLOAD_POST_USER),
        ("title", (title or "Untitled").strip()),
        ("async_upload", "true"),
        # Publish publicly — "share" means make it live.
        ("privacy_level", "PUBLIC_TO_EVERYONE"),  # TikTok
        ("privacyStatus", "public"),              # YouTube
        ("media_type", "REELS"),                  # Instagram
    ]
    for p in platforms:
        data.append(("platform[]", p))
    if caption:
        data.append(("description", caption))      # YouTube/Facebook/LinkedIn body
        data.append(("tiktok_title", caption[:2200]))
        data.append(("instagram_title", caption))

    headers = _headers()
    if idempotency_key:
        headers["Idempotency-Key"] = idempotency_key

    with path.open("rb") as fh:
        resp = requests.post(
            UPLOAD_URL,
            headers=headers,
            data=data,
            files={"video": (path.name, fh, "video/mp4")},
            timeout=300,
        )
    resp.raise_for_status()
    return resp.json()


def check_status(request_id: str) -> dict:
    """Poll an async upload's status; return the API's JSON response."""
    if not is_configured():
        raise NotConfigured("Set UPLOAD_POST_API_KEY and UPLOAD_POST_USER in your .env")
    resp = requests.get(
        STATUS_URL,
        headers=_headers(),
        params={"request_id": request_id},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()
