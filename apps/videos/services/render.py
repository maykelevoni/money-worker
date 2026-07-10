"""Assemble a vertical short with ffmpeg: pause-synced image slides + voiceover.

No on-screen captions and no music, by design. Each beat's image is shown from that
beat's start until the next beat starts (so pauses are covered, no black gaps),
scaled/cropped to fill 1080x1920. Every image is first normalised to exactly the
frame size so the concat step is reliable regardless of the source dimensions. The
final MP4 is stored through the storage API (local <-> R2). Replaces the old Kling
renderer.
"""
import shutil
import subprocess
import tempfile
from pathlib import Path

import requests
from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage

WIDTH, HEIGHT, FPS = 1080, 1920, 30
_FILL = f"scale={WIDTH}:{HEIGHT}:force_original_aspect_ratio=increase,crop={WIDTH}:{HEIGHT},setsar=1"


class RenderError(Exception):
    pass


def is_configured() -> bool:
    return shutil.which("ffmpeg") is not None


def _ffmpeg() -> str:
    exe = shutil.which("ffmpeg")
    if not exe:
        raise RenderError("ffmpeg not found on PATH")
    return exe


def _probe_duration(path: Path) -> float:
    exe = shutil.which("ffprobe")
    if not exe:
        return 0.0
    out = subprocess.run(
        [exe, "-v", "error", "-show_entries", "format=duration",
         "-of", "default=nw=1:nk=1", str(path)],
        capture_output=True, text=True,
    )
    try:
        return float(out.stdout.strip())
    except ValueError:
        return 0.0


def _fetch(dest: Path, url_or_name: str = "", fieldfile=None) -> None:
    """Copy a stored/remote asset to a local temp path (storage-agnostic)."""
    if fieldfile is not None:
        fieldfile.open("rb")
        try:
            dest.write_bytes(fieldfile.read())
        finally:
            fieldfile.close()
        return
    src = str(url_or_name)
    if src.startswith("http"):
        dest.write_bytes(requests.get(src, timeout=180).content)
        return
    name = src
    if settings.MEDIA_URL and name.startswith(settings.MEDIA_URL):
        name = name[len(settings.MEDIA_URL):]
    name = name.lstrip("/")
    fh = default_storage.open(name)
    try:
        dest.write_bytes(fh.read())
    finally:
        fh.close()


def render_short(video, filename: str = "") -> str:
    """Render the video's segments + voiceover into a vertical MP4; return its URL."""
    segs = list(video.segments.all())
    if not segs:
        raise RenderError("No segments to render — build and illustrate them first.")
    if not all(s.image for s in segs):
        raise RenderError("Some beats have no image yet — illustrate the segments first.")
    if not video.voice_url:
        raise RenderError("No voiceover — generate the voice first.")

    ffmpeg = _ffmpeg()
    tmp = Path(tempfile.mkdtemp(prefix="short_"))
    try:
        audio = tmp / "audio.wav"
        _fetch(audio, url_or_name=video.voice_url)
        audio_dur = _probe_duration(audio) or (segs[-1].end + 0.5)

        # Normalise every image to exactly the frame size (reliable concat).
        norm_paths = []
        for s in segs:
            raw = tmp / f"raw_{s.order}.png"
            norm = tmp / f"img_{s.order}.png"
            _fetch(raw, fieldfile=s.image)
            proc = subprocess.run(
                [ffmpeg, "-y", "-i", str(raw), "-vf", _FILL, "-frames:v", "1", str(norm)],
                capture_output=True, text=True,
            )
            if not norm.exists():
                raise RenderError(f"image normalise failed: {proc.stderr[-300:]}")
            norm_paths.append(norm)

        # Each image spans [beat.start, next beat.start]; first covers from 0, last to end.
        n = len(segs)
        bounds = [0.0] + [segs[i].start for i in range(1, n)] + [max(audio_dur, segs[-1].end)]
        durations = [max(0.2, bounds[i + 1] - bounds[i]) for i in range(n)]

        listfile = tmp / "list.txt"
        lines = []
        for p, d in zip(norm_paths, durations):
            lines.append(f"file '{p.as_posix()}'")
            lines.append(f"duration {d:.3f}")
        lines.append(f"file '{norm_paths[-1].as_posix()}'")  # concat needs the last repeated
        listfile.write_text("\n".join(lines))

        out = tmp / "out.mp4"
        proc = subprocess.run(
            [ffmpeg, "-y", "-f", "concat", "-safe", "0", "-i", str(listfile),
             "-i", str(audio),
             "-vf", f"fps={FPS},format=yuv420p",
             "-c:v", "libx264", "-preset", "veryfast",
             "-c:a", "aac", "-b:a", "128k", "-shortest", str(out)],
            capture_output=True, text=True,
        )
        if proc.returncode != 0 or not out.exists():
            raise RenderError(f"ffmpeg failed: {proc.stderr[-500:]}")

        name = filename or f"videos/short_{video.pk}.mp4"
        saved = default_storage.save(name, ContentFile(out.read_bytes()))
        return default_storage.url(saved)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
