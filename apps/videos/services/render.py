"""Render orchestrator — script + voiceover → scene images → assembled vertical MP4.

Faceless short-form is built as a captioned image slideshow over the AI voiceover
(the proven format), not a single "text-to-video" call. fal.ai makes the images;
ffmpeg (bundled, no sudo) stitches everything together.
"""
import re
from pathlib import Path

from django.conf import settings

from . import assemble, images, openrouter

MAX_SCENES = 6

IMAGE_STYLE = (
    "Modern flat vector illustration, clean explainer-video cartoon style, bold simple "
    "shapes, bright friendly colors, smooth gradients, consistent character design, "
    "minimal, family-friendly. Vertical 9:16 composition. Subject: {scene}"
)
# NOTE: we deliberately do NOT say "no text" here — naming text primes the model to
# draw it. Text suppression lives in images.NO_TEXT_NEGATIVE (negative_prompt).


class NotConfigured(Exception):
    pass


def is_configured() -> bool:
    return images.is_configured()


def _split_scenes(script: str, n: int = MAX_SCENES) -> list[str]:
    sentences = [s for s in re.split(r"(?<=[.!?])\s+", script.strip()) if s]
    if not sentences:
        return [script.strip()]
    if len(sentences) <= n:
        return sentences
    # merge sentences into n balanced chunks
    size = -(-len(sentences) // n)  # ceil
    return [
        " ".join(sentences[i : i + size]) for i in range(0, len(sentences), size)
    ]


def _voice_path(video) -> Path | None:
    if not video.voice_url:
        return None
    rel = video.voice_url.replace(settings.MEDIA_URL, "", 1)
    return Path(settings.MEDIA_ROOT) / rel


def render_video(video) -> str:
    """Produce a vertical MP4 for `video`; return its media URL."""
    if not images.is_configured():
        raise NotConfigured("Set FAL_API_KEY in your .env (needed for scene images)")
    if not video.script:
        raise NotConfigured("Generate the script first.")
    audio = _voice_path(video)
    if not audio or not audio.exists():
        raise NotConfigured("Generate the voiceover first.")

    scenes = _split_scenes(video.script)
    scene_dir = Path(settings.MEDIA_ROOT) / "scenes"
    style_seed = 1000 + video.pk  # same seed across scenes → consistent cartoon style

    # Draw a VISUAL of each scene, never the spoken words (stops baked-in gibberish text).
    try:
        visuals = openrouter.generate_scene_prompts(video.script, len(scenes))
    except Exception:
        visuals = []
    if len(visuals) != len(scenes):
        visuals = [f"an illustration representing: {s}" for s in scenes]

    image_paths = []
    for i, visual in enumerate(visuals):
        out = scene_dir / f"video_{video.pk}_{i}.png"
        images.generate_image(IMAGE_STYLE.format(scene=visual), out, seed=style_seed)
        image_paths.append(out)

    out_mp4 = Path(settings.MEDIA_ROOT) / "videos" / f"video_{video.pk}.mp4"
    assemble.assemble(image_paths, audio, scenes, out_mp4)
    return f"{settings.MEDIA_URL}videos/video_{video.pk}.mp4"
