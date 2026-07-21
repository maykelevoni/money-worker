"""Avatar portrait generation — the reusable engine behind the Duck Hacker.

Wraps the ideogram image step (services.images) so any character can be made the
same way: an appearance prompt + a fixed seed → a consistent 9:16 portrait saved
under media/character/. Text suppression (no gibberish baked in) comes for free.
"""
from pathlib import Path

from django.conf import settings

from . import images

NotConfigured = images.NotConfigured


def is_configured() -> bool:
    return images.is_configured()


def generate_portrait(avatar, reference_paths=None) -> str:
    """Generate `avatar`'s portrait, save it, point avatar.image at it; return media URL.

    If `reference_paths` are given (e.g. a photo, a cartoon, an inspiration image),
    the portrait is composed from them via nano-banana edit so the influencer can be
    based on a look the user has in mind. Otherwise it's a plain text-to-image render.
    """
    if not is_configured():
        raise NotConfigured("Set FAL_API_KEY in your .env (needed to generate avatars)")

    rel = f"character/avatar_{avatar.pk}.png"
    out = Path(settings.MEDIA_ROOT) / rel
    refs = [p for p in (reference_paths or []) if p]
    if refs:
        images.edit_image(avatar.appearance, refs, out)
    else:
        images.generate_image(
            avatar.appearance,
            out,
            seed=avatar.seed,
            style=avatar.style or "render_3D",
        )
    avatar.image.name = rel
    avatar.save(update_fields=["image"])
    return f"{settings.MEDIA_URL}{rel}"


def generate_full_body(avatar) -> str:
    """Turn the avatar's portrait into a full-body, front-facing image and save it to
    `avatar.body_image`. Used for Motion Clips, which need to see the whole body to map
    a dancer's skeleton onto the character. Identity is preserved via nano-banana/edit
    (the same identity-keeping edit used elsewhere), so the body's face matches the head.

    Returns the saved image's URL. Storage-agnostic (works with local disk or R2).
    """
    from django.core.files.base import ContentFile
    from django.core.files.storage import default_storage

    if not is_configured():
        raise NotConfigured("Set FAL_API_KEY in your .env (needed to generate the body)")
    if not avatar.image:
        raise ValueError("Generate the avatar's portrait first, then add a full body.")

    prompt = (
        f"{avatar.appearance}. Full-body shot of this exact same character from head to "
        "feet, standing upright and facing the camera, arms relaxed at the sides, both "
        "feet visible, the whole body centered in frame with headroom, on a plain seamless "
        "studio background. Keep the same face, hair, and outfit."
    )
    data = images.edit_scene_bytes(prompt, [avatar.image], aspect_ratio="9:16")
    name = default_storage.save(f"character/body_{avatar.pk}.png", ContentFile(data))
    avatar.body_image.name = name
    avatar.save(update_fields=["body_image"])
    return default_storage.url(name)
