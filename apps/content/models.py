from django.db import models

from apps.accounts.models import WorkspaceOwned
from apps.videos.services import uploadpost


class Post(WorkspaceOwned):
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

    # Where this came from, if spawned from a researched idea.
    source_idea = models.ForeignKey(
        "videos.TopicIdea",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="posts",
    )

    # --- Blog fields (only meaningful when kind == ARTICLE) ---
    website = models.ForeignKey(
        "sites.Website",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="articles",
        help_text="Which website's blog this article publishes to",
    )
    slug = models.SlugField(blank=True, help_text="Article URL on the blog")
    meta_description = models.TextField(blank=True, help_text="SEO description for the article")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["website", "slug"],
                condition=models.Q(website__isnull=False),
                name="uniq_article_slug_per_site",
            )
        ]

    def __str__(self):
        if self.title:
            return self.title
        if self.body:
            return self.body[:60]
        # Image posts with no caption yet: name them by what made the image.
        if self.kind == self.Kind.IMAGE and self.pk:
            img = self.images.filter(is_selected=True).first() or self.images.first()
            if img and img.prompt:
                return img.prompt[:60]
        return f"{self.get_kind_display()} #{self.pk}"

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


class PostImage(models.Model):
    """One image in a Post's gallery — generated, edited, or uploaded.

    A post builds up several; exactly one is `is_selected` (the one that publishes),
    which is mirrored into `Post.media` so the publish flow stays unchanged.
    """

    post = models.ForeignKey("content.Post", on_delete=models.CASCADE, related_name="images")
    image = models.FileField(upload_to="content/gallery/")
    prompt = models.CharField(max_length=500, blank=True, help_text="What made this image")
    is_selected = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"Image #{self.pk} of Post #{self.post_id}"

    @property
    def url(self):
        return self.image.url
