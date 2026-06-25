"""fal.ai image generation — one image per scene of the script."""
import os
from pathlib import Path

import requests
from django.conf import settings

RUN_URL = "https://fal.run/{model}"
# Ideogram v2 respects "no text" instructions; Flux/schnell did not and baked
# garbled letters into every frame. Override with FAL_IMAGE_MODEL if needed.
DEFAULT_MODEL = "fal-ai/ideogram/v2"


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
