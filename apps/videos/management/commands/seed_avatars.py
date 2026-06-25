"""Seed the canonical Duck Hacker avatar (idempotent).

Points at the already-generated reference image media/character/duck_hacker.png so it
shows up in the Avatars section without re-spending on generation.
"""
from django.core.management.base import BaseCommand

from apps.videos.models import Avatar

DUCK_APPEARANCE = (
    "An ADULT anthropomorphic duck hacker, intimidating scary villain, strong broad build, "
    "sharp aggressive features, furrowed brow, cold glowing RED eyes, visible neck, "
    "wearing a chunky knit BLACK WINTER BEANIE hat, headphones over the beanie, "
    "a FULL black jacket ZIPPED ALL THE WAY UP with LONG SLEEVES covering both arms, "
    "smooth closed beak, cinematic 3d animated character, dark moody horror lighting, high contrast"
)


class Command(BaseCommand):
    help = "Seed the canonical Duck Hacker avatar (idempotent)."

    def handle(self, *args, **options):
        duck, created = Avatar.objects.get_or_create(
            name="Duck Hacker",
            defaults={
                "appearance": DUCK_APPEARANCE,
                "style": "render_3D",
                "seed": 8101,
                "image": "character/duck_hacker.png",
                "is_default": True,
            },
        )
        self.stdout.write(
            self.style.SUCCESS("Created Duck Hacker avatar")
            if created
            else "Duck Hacker avatar already exists"
        )
