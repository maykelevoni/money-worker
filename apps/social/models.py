from django.db import models

from apps.accounts.models import WorkspaceOwned
from apps.videos.services import uploadpost


class SocialAccount(WorkspaceOwned):
    """A real social account you own — the target of publishing.

    Replaces loose platform strings: a post/video is sent to specific accounts.
    Posting runs through an Upload-Post profile (`up_profile`); several accounts
    can share a profile or each have their own.
    """

    class Platform(models.TextChoices):
        YOUTUBE = "youtube", "YouTube"
        TIKTOK = "tiktok", "TikTok"
        INSTAGRAM = "instagram", "Instagram"
        X = "x", "X"
        PINTEREST = "pinterest", "Pinterest"

    class Status(models.TextChoices):
        CONNECTED = "connected", "Connected"
        DISCONNECTED = "disconnected", "Not connected"
        ERROR = "error", "Error"

    platform = models.CharField(max_length=20, choices=Platform.choices)
    handle = models.CharField(max_length=120, help_text="e.g. @sleeptips")
    display_name = models.CharField(max_length=200, blank=True)
    up_profile = models.CharField(
        max_length=120,
        help_text="Upload-Post profile this account posts through",
    )
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.DISCONNECTED
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["platform", "handle"]

    def __str__(self):
        return f"{self.get_platform_display()} · {self.handle}"

    @property
    def platform_label(self):
        return uploadpost.PLATFORM_LABELS.get(self.platform, self.platform)
