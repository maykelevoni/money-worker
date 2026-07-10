"""Shorts pipeline orchestration.

Glues the services together for the vertical-shorts flow:
- `build_segments`  — voiceover → word timing → beats → VideoSegment rows.
- `illustrate_segments` — art-direct each beat → one nano-banana image per beat,
  featuring the avatar on the beats the art director picks.

Kept separate from the HTTP views so the pipeline is testable on its own.
"""
from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage

from ..models import VideoSegment
from . import images, openrouter, stt

# nano-banana tends to bake words into images; hammer the point in every prompt.
NO_TEXT = (
    " Absolutely NO text, words, letters, captions, numbers, signs, labels, logos, "
    "or writing of any kind anywhere in the image."
)


def _audio_source(video):
    """Return a source `stt.transcribe_timed` can read: an http URL (R2) as-is, or the
    stored voiceover opened from local/default storage."""
    url = video.voice_url or ""
    if url.startswith("http"):
        return url
    name = url
    if settings.MEDIA_URL and name.startswith(settings.MEDIA_URL):
        name = name[len(settings.MEDIA_URL):]
    name = name.lstrip("/")
    return default_storage.open(name)


def build_segments(video, gap: float = 0.4) -> int:
    """Transcribe the voiceover with timing, split it into beats on pauses, and
    (re)create the video's VideoSegment rows. Returns the number of beats."""
    if not video.voice_url:
        raise ValueError("Generate the voiceover before building segments.")

    words = stt.transcribe_timed(_audio_source(video))
    beats = stt.segment_by_pauses(words, gap=gap)

    video.segments.all().delete()
    VideoSegment.objects.bulk_create(
        [
            VideoSegment(
                video=video,
                order=i,
                text=b["text"],
                start=b["start"],
                end=b["end"],
            )
            for i, b in enumerate(beats)
        ]
    )
    return len(beats)


def illustrate_segments(video, on_progress=None) -> int:
    """Art-direct each beat and generate one image per segment (avatar-featuring where
    the art director chose it). Calls `on_progress(done, total)` per image. Returns the
    number of images made."""
    segments = list(video.segments.all())
    if not segments:
        raise ValueError("Build segments before illustrating them.")

    avatar = video.avatar if video.avatar_id else None
    subject = video.title or video.topic_idea or video.tool_featured or ""
    directions = openrouter.direct_beats(
        [s.text for s in segments],
        subject=subject,
        avatar_name=avatar.name if avatar else "",
    )

    total = len(segments)
    made = 0
    for seg, d in zip(segments, directions):
        if on_progress:
            on_progress(made + 1, total)
        prompt = d["prompt"]
        use_avatar = d["uses_avatar"] and bool(avatar and avatar.image)
        if use_avatar:
            data = images.edit_scene_bytes(prompt + NO_TEXT, [avatar.image])
        else:
            data = images.generate_scene_bytes(prompt + NO_TEXT)

        seg.image.save(f"seg_{video.pk}_{seg.order}.png", ContentFile(data), save=False)
        seg.image_prompt = prompt
        seg.uses_avatar = use_avatar
        seg.save(update_fields=["image", "image_prompt", "uses_avatar"])
        made += 1
    return made


def regenerate_segment(video, seg, use_avatar=None):
    """Redraw one segment's image (reusing its prompt). Pass `use_avatar` to force the
    avatar on/off for this beat; None keeps its current setting."""
    avatar = video.avatar if video.avatar_id else None
    if use_avatar is None:
        use_avatar = seg.uses_avatar
    use_avatar = bool(use_avatar) and bool(avatar and avatar.image)

    prompt = seg.image_prompt or seg.text
    if use_avatar:
        data = images.edit_scene_bytes(prompt + NO_TEXT, [avatar.image])
    else:
        data = images.generate_scene_bytes(prompt + NO_TEXT)

    seg.image.save(f"seg_{video.pk}_{seg.order}.png", ContentFile(data), save=False)
    seg.uses_avatar = use_avatar
    seg.save(update_fields=["image", "uses_avatar"])
    return seg


# ---- One-click, watchable generation (runs in a background thread) ----

def _run_pipeline(video_id):
    """Run the full short pipeline, writing progress onto the Video as it goes so the
    page can poll and show it. Runs in its own thread."""
    import threading  # noqa: F401  (kept explicit; import is cheap)

    from django.db import connections

    from ..models import Video
    from . import openrouter, render as render_svc, voice

    def step(msg):
        Video.objects.filter(pk=video_id).update(gen_status="running", gen_step=msg)

    try:
        video = Video.objects.get(pk=video_id)

        if not video.script:
            step("Writing the script…")
            subject = video.title or video.topic_idea or video.tool_featured or "this topic"
            pkg = openrouter.generate_script(subject, niche=video.niche)
            video.title = video.title or pkg["title"]
            video.hook, video.script, video.caption = pkg["hook"], pkg["script"], pkg["caption"]
            video.save()

        step("Cloning your voice…")
        avatar = video.avatar if video.avatar_id else None
        ref = avatar.voice_ref if avatar and avatar.voice_ref else None
        video.voice_url = voice.generate_voiceover(
            video.script, filename=f"video_{video.pk}.wav", ref_audio=ref
        )
        video.status = Video.Status.VOICED
        video.save(update_fields=["voice_url", "status"])

        step("Finding the beats in your voiceover…")
        build_segments(video)

        illustrate_segments(video, on_progress=lambda i, n: step(f"Illustrating beat {i} of {n}…"))

        step("Rendering the video…")
        url = render_svc.render_short(video)
        Video.objects.filter(pk=video_id).update(
            video_url=url, status=Video.Status.RENDERED, gen_status="done", gen_step="Done ✓"
        )
    except Exception as e:  # surface the reason to the page
        Video.objects.filter(pk=video_id).update(gen_status="error", gen_step=str(e)[:500])
    finally:
        connections.close_all()


def start_generation(video):
    """Kick off the full pipeline in a background thread; the page polls for progress."""
    import threading

    from ..models import Video

    Video.objects.filter(pk=video.pk).update(gen_status="running", gen_step="Starting…")
    threading.Thread(target=_run_pipeline, args=(video.pk,), daemon=True).start()
