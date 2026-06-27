from django.db import models


class Avatar(models.Model):
    """A reusable talking-video character (the Duck Hacker, and future ones).

    The same engine that produced the duck: an appearance prompt → ideogram image →
    (later) the talking-avatar pipeline. Niche-agnostic — a character, not a topic.
    """

    name = models.CharField(max_length=120)
    appearance = models.TextField(
        help_text="What the character looks like — used as the image generation prompt"
    )
    style = models.CharField(
        max_length=20,
        default="render_3D",
        help_text="Ideogram style: render_3D, design, realistic, anime, general",
    )
    seed = models.IntegerField(
        null=True,
        blank=True,
        help_text="Fixed seed → consistent look across regenerations",
    )
    image = models.FileField(upload_to="character/", blank=True)
    voice_id = models.CharField(
        max_length=120,
        blank=True,
        help_text="ElevenLabs voice id used to narrate as this character",
    )
    is_default = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-is_default", "-created_at"]

    def __str__(self):
        return self.name


class TopicIdea(models.Model):
    """A trending content idea surfaced by the research step, awaiting a pick."""

    headline = models.CharField(max_length=300, help_text="The viral topic/title")
    why_viral = models.TextField(
        blank=True, help_text="Why this is trending / likely to perform"
    )
    angle = models.TextField(
        blank=True, help_text="Suggested angle for the channel's niche"
    )
    selected = models.BooleanField(default=False, help_text="Picked → became a Video")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.headline


class Video(models.Model):
    """A faceless short-form video moving through the factory pipeline."""

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        SCRIPTED = "scripted", "Script ready"
        VOICED = "voiced", "Voiceover ready"
        RENDERED = "rendered", "Video rendered"
        APPROVED = "approved", "Approved"
        POSTED = "posted", "Posted"

    niche = models.CharField(
        max_length=200,
        blank=True,
        help_text="Free-form niche/topic for this video's channel (blank = niche-agnostic)",
    )
    avatar = models.ForeignKey(
        "videos.Avatar",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="videos",
        help_text="The character that presents/speaks this video",
    )

    tool_featured = models.CharField(
        max_length=200, blank=True, help_text="The subject/topic this video showcases"
    )

    # --- New front-end of the pipeline (idea → your voice → adapted script) ---
    topic_idea = models.CharField(
        max_length=300, blank=True, help_text="The chosen trending topic this video covers"
    )
    talking_points = models.TextField(
        blank=True, help_text="AI-suggested points you could cover on this topic"
    )
    source_audio = models.FileField(
        upload_to="source_audio/",
        blank=True,
        help_text="Your Portuguese voice memo explaining the idea your way",
    )
    transcript_pt = models.TextField(
        blank=True, help_text="Transcribed Portuguese from your voice memo"
    )

    title = models.CharField(max_length=300, blank=True)
    hook = models.CharField(max_length=300, blank=True)
    script = models.TextField(blank=True)
    caption = models.TextField(blank=True, help_text="Post caption + hashtags")

    voice_url = models.URLField(blank=True)
    video_url = models.URLField(blank=True, help_text="Rendered video (fal.ai output)")

    offer = models.ForeignKey(
        "offers.Offer",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="videos",
    )
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.DRAFT
    )

    posted_at = models.DateTimeField(null=True, blank=True)

    # --- Social sharing (Upload-Post) ---
    share_request_id = models.CharField(
        max_length=120, blank=True, help_text="Upload-Post async request id, for status polling"
    )
    share_status = models.CharField(
        max_length=20, blank=True, help_text="'' | pending | done | failed"
    )
    share_results = models.JSONField(
        default=dict, blank=True, help_text="Per-platform result (url/error) from Upload-Post"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return (
            self.title
            or self.topic_idea
            or (f"Video on {self.tool_featured}" if self.tool_featured else "Untitled video")
        )
