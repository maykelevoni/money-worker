"""Upload-Post client — publishes a rendered video to YouTube / TikTok /
Instagram through one unified API, so we don't fight each platform's native
posting API (TikTok app audits, the Instagram/Facebook review, YouTube quota).

Docs: https://docs.upload-post.com/api/upload-video/
"""
import requests
from django.conf import settings

UPLOAD_URL = "https://api.upload-post.com/api/upload"
PHOTO_URL = "https://api.upload-post.com/api/upload_photos"
TEXT_URL = "https://api.upload-post.com/api/upload_text"
STATUS_URL = "https://api.upload-post.com/api/uploadposts/status"

# The platforms we expose in the UI today (video path).
PLATFORMS = ["youtube", "tiktok", "instagram"]
PLATFORM_LABELS = {
    "youtube": "YouTube", "tiktok": "TikTok", "instagram": "Instagram",
    "x": "X", "pinterest": "Pinterest",
}

# Which channels each kind of content can actually be published to.
KIND_CHANNELS = {
    "video": ["youtube", "tiktok", "instagram", "x"],
    "image": ["instagram", "tiktok", "x", "pinterest"],
    "text": ["x"],
    "article": [],  # articles publish to the blog, not social (repurpose later)
}


class NotConfigured(Exception):
    pass


def is_configured() -> bool:
    return bool(settings.UPLOAD_POST_API_KEY and settings.UPLOAD_POST_USER)


def _headers() -> dict:
    return {"Authorization": f"Apikey {settings.UPLOAD_POST_API_KEY}"}


def upload_video(fileobj, filename, platforms, title, caption="", *, idempotency_key=""):
    """Post a video (open file object) to `platforms`; return the API's JSON.

    Taking a file object rather than a path keeps this backend-agnostic — the
    caller opens it via local disk or R2. `title` is required by YouTube;
    `caption` becomes the description/body where each platform supports it.
    Uploads run async, so the response carries a `request_id` for `check_status`.
    """
    if not is_configured():
        raise NotConfigured("Set UPLOAD_POST_API_KEY and UPLOAD_POST_USER in your .env")

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

    resp = requests.post(
        UPLOAD_URL,
        headers=headers,
        data=data,
        files={"video": (filename, fileobj, "video/mp4")},
        timeout=300,
    )
    resp.raise_for_status()
    return resp.json()


def upload_photo(fileobj, filename, platforms, title, caption="", *, idempotency_key=""):
    """Post a single image (open file object) to `platforms`
    (Instagram/TikTok/X/Pinterest…). `title` is the caption.
    """
    if not is_configured():
        raise NotConfigured("Set UPLOAD_POST_API_KEY and UPLOAD_POST_USER in your .env")

    data = [("user", settings.UPLOAD_POST_USER), ("title", (title or caption or "").strip())]
    for p in platforms:
        data.append(("platform[]", p))
    if caption:
        data.append(("description", caption))

    headers = _headers()
    if idempotency_key:
        headers["Idempotency-Key"] = idempotency_key

    resp = requests.post(
        PHOTO_URL,
        headers=headers,
        data=data,
        files=[("photos[]", (filename, fileobj, "image/png"))],
        timeout=300,
    )
    resp.raise_for_status()
    return resp.json()


def upload_text(platforms, title, description="", *, idempotency_key=""):
    """Post a text-only update to `platforms` (X/LinkedIn/Threads/Reddit…)."""
    if not is_configured():
        raise NotConfigured("Set UPLOAD_POST_API_KEY and UPLOAD_POST_USER in your .env")
    data = [("user", settings.UPLOAD_POST_USER), ("title", (title or "").strip())]
    for p in platforms:
        data.append(("platform[]", p))
    if description:
        data.append(("description", description))

    headers = _headers()
    if idempotency_key:
        headers["Idempotency-Key"] = idempotency_key

    resp = requests.post(TEXT_URL, headers=headers, data=data, timeout=60)
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
