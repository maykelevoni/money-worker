from django.db import models

from apps.accounts.models import WorkspaceOwned


class Avatar(WorkspaceOwned):
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
        help_text="Legacy ElevenLabs voice id (unused since the F5-TTS swap)",
    )
    voice_ref = models.FileField(
        upload_to="voice_refs/",
        blank=True,
        help_text="A short, clean clip of the target voice — the F5-TTS cloning reference",
    )
    is_default = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-is_default", "-created_at"]

    def __str__(self):
        return self.name


class TopicIdea(WorkspaceOwned):
    """A researched topic surfaced by the Topic Explorer — data + a plain-English
    description — that you can scan, filter, and turn into content."""

    class Intent(models.TextChoices):
        HOWTO = "how-to", "How-to"
        IDEAS = "ideas", "Ideas"
        QUESTION = "question", "Question"
        COMMERCIAL = "commercial", "Commercial"
        NEWS = "news", "News"

    class Trend(models.TextChoices):
        UP = "up", "Rising"
        FLAT = "flat", "Steady"
        DOWN = "down", "Cooling"

    headline = models.CharField(max_length=300, help_text="The topic / keyword phrase")
    seed = models.CharField(
        max_length=200, blank=True, help_text="The seed term this topic came from (blank = open)"
    )
    description = models.TextField(
        blank=True, help_text="Plain-English 'what this is' — understand the topic"
    )
    why_viral = models.TextField(
        blank=True, help_text="Why this is trending / likely to perform"
    )
    angle = models.TextField(
        blank=True, help_text="Suggested content angle for this topic"
    )

    # --- Research data (AI-estimated; trend line enriched from Google Trends) ---
    search_volume = models.IntegerField(
        null=True, blank=True, help_text="Estimated monthly searches"
    )
    difficulty = models.IntegerField(
        null=True, blank=True, help_text="Estimated SEO difficulty 0-100"
    )
    intent = models.CharField(
        max_length=20, choices=Intent.choices, blank=True, help_text="Search intent"
    )
    trend_dir = models.CharField(
        max_length=8, choices=Trend.choices, blank=True, help_text="Momentum direction"
    )
    trend_pct = models.IntegerField(
        null=True, blank=True, help_text="Estimated year-over-year interest change (%)"
    )
    related = models.JSONField(
        default=list, blank=True, help_text="Related / rising queries"
    )

    selected = models.BooleanField(default=False, help_text="Legacy: first pick consumed the idea")
    archived = models.BooleanField(
        default=False, help_text="Hidden from research — cleared out after use"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def volume_display(self) -> str:
        """Human volume band, e.g. 8100 → '8.1k'."""
        v = self.search_volume
        if v is None:
            return "—"
        if v >= 1000:
            return f"{v / 1000:.1f}k".replace(".0k", "k")
        return str(v)

    @property
    def difficulty_dots(self) -> str:
        """Difficulty as a 5-dot meter, e.g. 34 → '●●●○○'."""
        if self.difficulty is None:
            return "○○○○○"
        filled = max(0, min(5, round(self.difficulty / 20)))
        return "●" * filled + "○" * (5 - filled)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.headline


class Video(WorkspaceOwned):
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

    # Where this came from, if spawned from a researched idea.
    source_idea = models.ForeignKey(
        "videos.TopicIdea",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="videos",
        help_text="The researched idea this video was spawned from",
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

    # --- One-click generation progress (watchable pipeline) ---
    gen_status = models.CharField(
        max_length=12, blank=True, help_text="'' | running | done | error"
    )
    gen_step = models.TextField(
        blank=True, help_text="Human-readable current step (or the error message)"
    )

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


class VideoSegment(models.Model):
    """One beat of a short: a spoken phrase, its time window in the voiceover, and the
    image shown for it.

    Segments come from splitting the voiceover on natural pauses. Each gets a *conceptual*
    image (an illustration of what's said, not a literal shot), and some beats feature the
    avatar character. This is the backbone of the pause-synced slideshow the renderer
    stitches together.
    """

    video = models.ForeignKey(
        "videos.Video", on_delete=models.CASCADE, related_name="segments"
    )
    order = models.PositiveIntegerField(default=0)
    text = models.TextField(blank=True, help_text="The spoken phrase for this beat")
    start = models.FloatField(default=0.0, help_text="Start time in the voiceover (seconds)")
    end = models.FloatField(default=0.0, help_text="End time in the voiceover (seconds)")

    image = models.FileField(upload_to="video_segments/", blank=True)
    image_prompt = models.TextField(
        blank=True, help_text="Art-director prompt used to generate this beat's image"
    )
    uses_avatar = models.BooleanField(
        default=False, help_text="Whether this beat's image features the avatar character"
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["video", "order"]

    def __str__(self):
        return f"{self.video_id} · #{self.order} · {self.text[:40]}"

    @property
    def duration(self) -> float:
        """Seconds this slide is on screen."""
        return max(0.0, self.end - self.start)
