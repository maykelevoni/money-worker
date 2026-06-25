"""ffmpeg assembly — images + voiceover + captions → vertical MP4.

Uses the static ffmpeg binary bundled by imageio-ffmpeg (no system install / sudo).
"""
import re
import subprocess
from pathlib import Path

import imageio_ffmpeg

W, H = 1080, 1920  # TikTok / Shorts / Reels vertical


def ffmpeg_exe() -> str:
    return imageio_ffmpeg.get_ffmpeg_exe()


def audio_duration(path: Path) -> float:
    """Read an audio file's duration (seconds) by parsing ffmpeg's output."""
    proc = subprocess.run(
        [ffmpeg_exe(), "-i", str(path)],
        capture_output=True,
        text=True,
    )
    m = re.search(r"Duration:\s*(\d+):(\d+):(\d+\.\d+)", proc.stderr)
    if not m:
        return 0.0
    h, mnt, s = m.groups()
    return int(h) * 3600 + int(mnt) * 60 + float(s)


def _ass_ts(seconds: float) -> str:
    """ASS timestamp: H:MM:SS.cc (centiseconds)."""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds % 60
    return f"{h:d}:{m:02d}:{s:05.2f}"


# ASS header: PlayRes locked to the real video size so FontSize is in true pixels.
# Big bold white text with a thick black outline, sitting in the lower third.
_ASS_HEADER = """[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 2

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Arial,68,&H00FFFFFF,&H00000000,&H00000000,1,0,0,0,100,100,0,0,1,5,0,2,90,90,300,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""


def build_ass(full_text: str, total: float, path: Path, words_per_cue: int = 3) -> Path:
    """Write an .ass caption track: short word-chunks popping in time with the voice."""
    words = full_text.replace("\n", " ").split()
    if not words:
        path.write_text(_ASS_HEADER, encoding="utf-8")
        return path
    per_word = total / len(words)
    events, idx = [], 0
    t = 0.0
    while idx < len(words):
        chunk = words[idx : idx + words_per_cue]
        start = t
        end = t + per_word * len(chunk)
        t = end
        idx += len(chunk)
        text = " ".join(chunk).replace("\\", "").strip()
        events.append(
            f"Dialogue: 0,{_ass_ts(start)},{_ass_ts(end)},Default,,0,0,0,,{text}"
        )
    path.write_text(_ASS_HEADER + "\n".join(events) + "\n", encoding="utf-8")
    return path


FPS = 30
# Upscale before zooming so the pan/zoom stays smooth (no pixel jitter).
SS_W, SS_H = W * 2, H * 2


def assemble(
    image_paths: list[Path],
    audio_path: Path,
    captions: list[str],
    out_path: Path,
) -> Path:
    """Build a vertical MP4 from images, voiceover and captions.

    Each image becomes a clip with a slow Ken Burns pan/zoom (alternating in/out)
    so the video feels alive instead of a static slideshow.
    """
    n = max(len(image_paths), 1)
    total = audio_duration(audio_path) or (n * 3.0)
    per = total / n
    frames = max(int(round(per * FPS)), 1)

    workdir = out_path.parent
    workdir.mkdir(parents=True, exist_ok=True)
    # Captions are timed across the whole voiceover, in short word-chunks.
    ass = build_ass(" ".join(captions), total, workdir / f"{out_path.stem}.ass")

    # One input per image (single still frame each), then the audio last.
    inputs = []
    for img in image_paths:
        inputs += ["-i", str(img.resolve())]
    audio_idx = len(image_paths)
    inputs += ["-i", str(audio_path.resolve())]

    # Per-image zoompan: even scenes zoom in, odd scenes zoom out — gentle variety.
    parts = []
    for i in range(len(image_paths)):
        if i % 2 == 0:
            z = "min(zoom+0.0012,1.18)"           # slow zoom in
        else:
            z = "if(eq(on,0),1.18,max(zoom-0.0012,1.0))"  # slow zoom out
        parts.append(
            f"[{i}:v]scale={SS_W}:{SS_H}:force_original_aspect_ratio=increase,"
            f"crop={SS_W}:{SS_H},"
            f"zoompan=z='{z}':d={frames}:"
            f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
            f"fps={FPS}:s={W}x{H},setsar=1[v{i}]"
        )

    concat_in = "".join(f"[v{i}]" for i in range(len(image_paths)))
    filter_complex = (
        ";".join(parts)
        + f";{concat_in}concat=n={len(image_paths)}:v=1:a=0[vcat]"
        + f";[vcat]subtitles='{ass.resolve()}'[vout]"
    )

    cmd = [
        ffmpeg_exe(), "-y",
        *inputs,
        "-filter_complex", filter_complex,
        "-map", "[vout]", "-map", f"{audio_idx}:a",
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-r", str(FPS),
        "-c:a", "aac", "-b:a", "192k",
        "-shortest",
        str(out_path),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg failed:\n{proc.stderr[-1500:]}")
    return out_path
