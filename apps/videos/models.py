from django.db import models


class TopicIdea(models.Model):
    """A trending content idea surfaced by the research step, awaiting a pick."""

    headline = models.CharField(max_length=300, help_text="The viral topic/title")
    why_viral = models.TextField(
        blank=True, help_text="Why this is trending / likely to perform"
    )
    angle = models.TextField(
        blank=True, help_text="Suggested angle for our AI-tools-for-creators lane"
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

    tool_featured = models.CharField(
        max_length=200, blank=True, help_text="The AI tool this video showcases"
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
