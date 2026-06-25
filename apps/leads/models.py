from django.db import models


class Lead(models.Model):
    """An email captured through the funnel."""

    class Stage(models.TextChoices):
        NEW = "new", "New"
        NURTURING = "nurturing", "Nurturing"
        CLICKED = "clicked", "Clicked offer"
        CONVERTED = "converted", "Converted"

    email = models.EmailField(unique=True)
    source_video = models.ForeignKey(
        "videos.Video",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="leads",
    )
    lead_magnet = models.CharField(
        max_length=200, blank=True, help_text="Freebie they opted in for"
    )
    stage = models.CharField(
        max_length=20, choices=Stage.choices, default=Stage.NEW
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.email
