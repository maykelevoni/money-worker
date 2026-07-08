"""fal.ai image generation — text-to-image, plus multi-reference image editing."""
import base64
import mimetypes
import os
from pathlib import Path

import requests
from django.conf import settings

RUN_URL = "https://fal.run/{model}"
# Ideogram v2 respects "no text" instructions; Flux/schnell did not and baked
# garbled letters into every frame. Override with FAL_IMAGE_MODEL if needed.
DEFAULT_MODEL = "fal-ai/ideogram/v2"
# Multi-image editor: takes a prompt + up to ~14 reference images and composes/edits
# from them. Override with FAL_EDIT_MODEL.
DEFAULT_EDIT_MODEL = "fal-ai/nano-banana/edit"


class NotConfigured(Exception):
    pass


def is_configured() -> bool:
    return bool(settings.FAL_API_KEY)


def _build_payload(
    model: str, prompt: str, seed: int | None, negative_prompt: str, style: str
) -> dict:
    """Per-model request body (Ideogram and Flux take different params)."""
    if "ideogram" in model:
        payload = {
            "prompt": prompt,
            "aspect_ratio": "9:16",          # vertical, matches 1080x1920
            "style": style,                  # design=flat graphic, render_3D=Pixar-ish, etc.
            "expand_prompt": False,          # draw OUR prompt, don't let MagicPrompt rewrite it
            "negative_prompt": negative_prompt,
        }
    else:  # Flux-family fallback
        payload = {
            "prompt": prompt,
            "image_size": "portrait_16_9",
            "num_images": 1,
        }
    if seed is not None:
        payload["seed"] = seed
    return payload


# Things we never want drawn into the frame. Goes in a real negative_prompt
# channel (Ideogram) — NOT appended to the positive prompt, where it backfires.
NO_TEXT_NEGATIVE = (
    "text, words, letters, captions, typography, signage, logo, watermark, "
    "label, subtitle, gibberish, deformed hands"
)


def generate_image(
    prompt: str,
    out_path: Path,
    seed: int | None = None,
    negative_prompt: str = NO_TEXT_NEGATIVE,
    style: str = "design",
) -> Path:
    """Generate one portrait image for `prompt` and save it to `out_path`.

    Pass a fixed `seed` to keep a consistent look across a video's scenes.
    `style` (Ideogram): design | render_3D | realistic | anime | general | auto.
    """
    if not is_configured():
        raise NotConfigured("Set FAL_API_KEY in your .env")

    model = os.getenv("FAL_IMAGE_MODEL", DEFAULT_MODEL)
    payload = _build_payload(model, prompt, seed, negative_prompt, style)
    resp = requests.post(
        RUN_URL.format(model=model),
        headers={
            "Authorization": f"Key {settings.FAL_API_KEY}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=120,
    )
    resp.raise_for_status()
    data = resp.json()
    url = data["images"][0]["url"]

    img = requests.get(url, timeout=120)
    img.raise_for_status()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(img.content)
    return out_path


def _data_uri(path: Path) -> str:
    """Encode a local image file as a base64 data URI (fal accepts these as inputs)."""
    mime = mimetypes.guess_type(str(path))[0] or "image/png"
    b64 = base64.b64encode(Path(path).read_bytes()).decode("ascii")
    return f"data:{mime};base64,{b64}"


def edit_image(prompt: str, reference_paths: list[Path], out_path: Path) -> Path:
    """Compose/edit an image from a prompt + one or more reference images.

    Feeds the references to a multi-image model (nano-banana by default) so you can
    iterate ("make the background purple") or blend several inputs. Save to `out_path`.
    """
    if not is_configured():
        raise NotConfigured("Set FAL_API_KEY in your .env")
    refs = [p for p in reference_paths if p and Path(p).exists()]
    if not refs:
        raise ValueError("edit_image needs at least one reference image.")

    model = os.getenv("FAL_EDIT_MODEL", DEFAULT_EDIT_MODEL)
    payload = {
        "prompt": prompt,
        "image_urls": [_data_uri(p) for p in refs[:14]],
        "num_images": 1,
    }
    resp = requests.post(
        RUN_URL.format(model=model),
        headers={
            "Authorization": f"Key {settings.FAL_API_KEY}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=180,
    )
    resp.raise_for_status()
    data = resp.json()
    url = data["images"][0]["url"]

    img = requests.get(url, timeout=120)
    img.raise_for_status()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(img.content)
    return out_path
