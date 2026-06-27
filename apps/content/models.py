from django.db import models

from apps.videos.services import uploadpost


class Post(models.Model):
    """A unit of content in the hub — written here or pulled from the Video
    Factory — that gets organised, scheduled and published to social channels.

    One model covers every kind (text / image / video / article); the `kind`
    decides which channels apply and which Upload-Post endpoint publishes it.
    """

    class Kind(models.TextChoices):
        TEXT = "text", "Text post"
        IMAGE = "image", "Image"
        VIDEO = "video", "Video"
        ARTICLE = "article", "Article / blog"

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        SCHEDULED = "scheduled", "Scheduled"
        PUBLISHING = "publishing", "Publishing"
        POSTED = "posted", "Posted"
        FAILED = "failed", "Failed"

    kind = models.CharField(max_length=12, choices=Kind.choices, default=Kind.TEXT)
    title = models.CharField(max_length=300, blank=True)
    body = models.TextField(blank=True, help_text="Caption for social, or the article body")

    media = models.FileField(
        upload_to="content/", blank=True, help_text="Image or video — stored in R2 when configured"
    )
    media_url = models.URLField(blank=True, help_text="External media URL (e.g. a rendered video)")

    channels = models.JSONField(default=list, blank=True, help_text="Target channels to publish to")
    scheduled_at = models.DateTimeField(null=True, blank=True, help_text="When to publish (blank = now)")

    status = models.CharField(max_length=12, choices=Status.choices, default=Status.DRAFT)

    # Upload-Post tracking — same pattern as Video.
    share_request_id = models.CharField(max_length=120, blank=True)
    share_results = models.JSONField(default=dict, blank=True)

    # Where this came from, if repurposed from a factory video.
    source_video = models.ForeignKey(
        "videos.Video",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="content_posts",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.title or (self.body[:50] if self.body else f"{self.get_kind_display()} #{self.pk}")

    @property
    def media_src(self):
        """Public URL for the media, whether it's stored in R2 or external."""
        if self.media:
            return self.media.url
        return self.media_url

    @property
    def available_channels(self):
        """Channels this kind of content can actually be published to."""
        return uploadpost.KIND_CHANNELS.get(self.kind, [])

    @property
    def channel_labels(self):
        return [uploadpost.PLATFORM_LABELS.get(c, c) for c in self.channels]
