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


def illustrate_segments(video) -> int:
    """Art-direct each beat and generate one image per segment (avatar-featuring where
    the art director chose it). Returns the number of images made."""
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

    made = 0
    for seg, d in zip(segments, directions):
        prompt = d["prompt"]
        use_avatar = d["uses_avatar"] and bool(avatar and avatar.image)
        if use_avatar:
            data = images.edit_scene_bytes(prompt, [avatar.image])
        else:
            data = images.generate_scene_bytes(prompt)

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
        data = images.edit_scene_bytes(prompt, [avatar.image])
    else:
        data = images.generate_scene_bytes(prompt)

    seg.image.save(f"seg_{video.pk}_{seg.order}.png", ContentFile(data), save=False)
    seg.uses_avatar = use_avatar
    seg.save(update_fields=["image", "uses_avatar"])
    return seg
