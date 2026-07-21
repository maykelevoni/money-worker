"""Motion Clip generation — the avatar performs a reference video's movement.

Feeds the avatar's (full-body) image + an uploaded reference video to fal-ai/wan-motion,
which retargets the reference's skeleton onto the character and returns a new clip of the
avatar doing that motion. Only the movement is taken — the reference footage never appears
in the output.

Runs in a background thread, writing progress onto the Video (the same watchable pattern
as the shorts pipeline), so the page can poll `short_status` for step + result. Uploads
and the model call use the FAL REST + queue endpoints the app already relies on (the
`alpha` storage upload that Whisper uses) — not the fal_client library.
"""
import time

import requests
from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage

MODEL = "fal-ai/wan-motion"
UPLOAD_INITIATE_URL = "https://rest.alpha.fal.ai/storage/upload/initiate"
QUEUE_URL = "https://queue.fal.run/{model}"


class NotConfigured(Exception):
    pass


def is_configured() -> bool:
    return bool(settings.FAL_API_KEY)


def _headers(json: bool = False) -> dict:
    h = {"Authorization": f"Key {settings.FAL_API_KEY}"}
    if json:
        h["Content-Type"] = "application/json"
    return h


def _upload(data: bytes, content_type: str, file_name: str) -> str:
    """Upload bytes to FAL storage, return the hosted URL (initiate → signed PUT)."""
    init = requests.post(
        UPLOAD_INITIATE_URL,
        headers=_headers(json=True),
        json={"content_type": content_type, "file_name": file_name},
        timeout=60,
    )
    init.raise_for_status()
    j = init.json()
    put = requests.put(
        j["upload_url"], data=data, headers={"Content-Type": content_type}, timeout=600
    )
    put.raise_for_status()
    return j["file_url"]


def _run_queue(arguments: dict, on_poll=None, timeout: int = 900) -> dict:
    """Submit a job to the FAL queue and poll until it completes; return the result."""
    sub = requests.post(
        QUEUE_URL.format(model=MODEL), headers=_headers(json=True), json=arguments, timeout=60
    )
    sub.raise_for_status()
    req_id = sub.json()["request_id"]
    base = f"https://queue.fal.run/{MODEL}/requests/{req_id}"
    deadline = time.time() + timeout
    while time.time() < deadline:
        st = requests.get(base + "/status", headers=_headers(), timeout=30).json()
        status = st.get("status")
        if status == "COMPLETED":
            return requests.get(base, headers=_headers(), timeout=120).json()
        if status in ("FAILED", "ERROR"):
            raise RuntimeError(f"FAL motion job failed: {st}")
        if on_poll:
            on_poll()
        time.sleep(3)
    raise TimeoutError("Motion render timed out")


def _character_image(video):
    """The image to animate: prefer the avatar's full body, else its portrait."""
    avatar = video.avatar if video.avatar_id else None
    if avatar is None:
        return None
    return avatar.body_image if avatar.body_image else (avatar.image or None)


def _read(fieldfile) -> bytes:
    fieldfile.open("rb")
    try:
        return fieldfile.read()
    finally:
        fieldfile.close()


def _run(video_id):
    from django.db import connections

    from ..models import Video

    def step(msg):
        Video.objects.filter(pk=video_id).update(gen_status="running", gen_step=msg)

    try:
        video = Video.objects.get(pk=video_id)

        img = _character_image(video)
        if img is None:
            raise RuntimeError("Pick an avatar with an image first (or give it a full body).")
        if not video.motion_ref:
            raise RuntimeError("Upload a reference video to copy the movement from.")

        step("Uploading character + reference to FAL…")
        img_url = _upload(_read(img), "image/png", f"avatar_{video_id}.png")
        vid_url = _upload(_read(video.motion_ref), "video/mp4", f"motion_{video_id}.mp4")

        step("Animating the character — this takes ~2 minutes…")
        result = _run_queue(
            {
                "image_url": img_url,
                "video_url": vid_url,
                "prompt": (
                    video.script
                    or "the character performing the reference movement, plain background"
                ),
            },
            on_poll=lambda: step("Animating the character — this takes ~2 minutes…"),
        )

        out_url = (result.get("video") or {}).get("url")
        if not out_url:
            raise RuntimeError(f"No video in the FAL result: {result}")

        step("Saving the video…")
        data = requests.get(out_url, timeout=600).content
        saved = default_storage.save(f"videos/motion_{video_id}.mp4", ContentFile(data))
        Video.objects.filter(pk=video_id).update(
            video_url=default_storage.url(saved),
            status=Video.Status.RENDERED,
            gen_status="done",
            gen_step="Done ✓",
        )
    except Exception as e:  # surface the reason to the page
        Video.objects.filter(pk=video_id).update(gen_status="error", gen_step=str(e)[:500])
    finally:
        connections.close_all()


def start_motion(video):
    """Kick off the motion render in a background thread; the page polls for progress."""
    import threading

    from ..models import Video

    Video.objects.filter(pk=video.pk).update(gen_status="running", gen_step="Starting…")
    threading.Thread(target=_run, args=(video.pk,), daemon=True).start()
