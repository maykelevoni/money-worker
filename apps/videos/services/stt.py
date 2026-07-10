"""Speech-to-text — transcribes audio via fal.ai Whisper.

Two jobs:
- `transcribe()` — plain text from a voice memo (front of the pipeline: Mayke
  records an idea his way; this turns it into text for the LLM to adapt).
- `transcribe_timed()` + `segment_by_pauses()` — word-level timing for the shorts
  renderer: split the generated voiceover into beats on natural pauses, so one
  image can be shown per beat (the pause-synced slideshow).

Reuses the existing FAL_API_KEY (same key as image generation).
"""
from pathlib import Path

import requests
from django.conf import settings

MODEL_URL = "https://fal.run/fal-ai/whisper"
UPLOAD_INITIATE_URL = "https://rest.alpha.fal.ai/storage/upload/initiate"

_MIME = {
    ".mp3": "audio/mpeg",
    ".m4a": "audio/mp4",
    ".mp4": "audio/mp4",
    ".wav": "audio/wav",
    ".ogg": "audio/ogg",
    ".oga": "audio/ogg",
    ".webm": "audio/webm",
    ".flac": "audio/flac",
}


class NotConfigured(Exception):
    pass


def is_configured() -> bool:
    return bool(settings.FAL_API_KEY)


def _fal_upload(data: bytes, content_type: str, file_name: str) -> str:
    """Upload bytes to FAL storage and return the hosted file URL.

    Whisper rejects data-URI audio ("Unsupported data URL"), so audio must be a real
    URL. Two steps: initiate (get a signed PUT url + final file url), then PUT the bytes.
    """
    init = requests.post(
        UPLOAD_INITIATE_URL,
        headers={"Authorization": f"Key {settings.FAL_API_KEY}", "Content-Type": "application/json"},
        json={"content_type": content_type, "file_name": file_name},
        timeout=60,
    )
    init.raise_for_status()
    j = init.json()
    put = requests.put(j["upload_url"], data=data, headers={"Content-Type": content_type}, timeout=300)
    put.raise_for_status()
    return j["file_url"]


def _audio_url_for(source) -> str:
    """Return a Whisper-fetchable URL for `source`: an http(s) URL is passed through; a
    local path or FieldFile is uploaded to FAL storage first."""
    if isinstance(source, str) and source.startswith("http"):
        return source
    if hasattr(source, "read"):  # a FieldFile / file-like
        source.open("rb")
        try:
            data = source.read()
        finally:
            source.close()
        name = getattr(source, "name", "audio.wav")
    else:
        path = Path(source)
        data = path.read_bytes()
        name = path.name
    mime = _MIME.get(Path(name).suffix.lower(), "audio/mpeg")
    return _fal_upload(data, mime, Path(name).name)


def transcribe(audio_path, language: str = "pt") -> str:
    """Transcribe an audio file. Defaults to Portuguese; returns plain text."""
    if not is_configured():
        raise NotConfigured("Set FAL_API_KEY in your .env (needed for transcription)")

    path = Path(audio_path)
    if not path.exists():
        raise FileNotFoundError(f"Audio file not found: {path}")

    resp = requests.post(
        MODEL_URL,
        headers={
            "Authorization": f"Key {settings.FAL_API_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "audio_url": _audio_url_for(path),
            "task": "transcribe",
            "language": language,
        },
        timeout=300,
    )
    resp.raise_for_status()
    data = resp.json()
    return (data.get("text") or "").strip()


def transcribe_timed(source, language: str = "en") -> list[dict]:
    """Transcribe with word-level timing.

    `source` may be an http(s) URL (e.g. an R2 voiceover), a data URI, a local path,
    or a FieldFile. Returns a list of `{"text", "start", "end"}` words (seconds).
    """
    if not is_configured():
        raise NotConfigured("Set FAL_API_KEY in your .env (needed for transcription)")

    resp = requests.post(
        MODEL_URL,
        headers={
            "Authorization": f"Key {settings.FAL_API_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "audio_url": _audio_url_for(source),
            "task": "transcribe",
            "language": language,
            "chunk_level": "word",
        },
        timeout=300,
    )
    resp.raise_for_status()
    words = []
    for c in resp.json().get("chunks") or []:
        ts = c.get("timestamp") or [None, None]
        if ts[0] is None:
            continue
        start = float(ts[0])
        end = float(ts[1]) if ts[1] is not None else start
        words.append({"text": (c.get("text") or "").strip(), "start": start, "end": end})
    return words


def segment_by_pauses(words: list[dict], gap: float = 0.4, max_chars: int = 140) -> list[dict]:
    """Group timed words into beats, breaking on a silence gap > `gap` seconds (or
    when a beat would exceed `max_chars`). Returns `{"text", "start", "end"}` beats."""

    def _beat(ws):
        return {
            "text": " ".join(w["text"] for w in ws).strip(),
            "start": ws[0]["start"],
            "end": ws[-1]["end"],
        }

    beats: list[dict] = []
    cur: list[dict] = []
    for w in words:
        if cur:
            prev_end = cur[-1]["end"]
            too_long = len(" ".join(x["text"] for x in cur)) > max_chars
            if (w["start"] - prev_end) > gap or too_long:
                beats.append(_beat(cur))
                cur = []
        cur.append(w)
    if cur:
        beats.append(_beat(cur))
    return beats
