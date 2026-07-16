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
