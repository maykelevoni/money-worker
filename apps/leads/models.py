from django.db import models
from django.urls import reverse

from apps.accounts.models import WorkspaceOwned


class EmailList(WorkspaceOwned):
    """A named audience. Leads from different sources join different lists so
    they can be seen, filtered and nurtured separately."""

    name = models.CharField(max_length=200)
    description = models.CharField(max_length=300, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    @classmethod
    def default_for(cls, workspace):
        obj, _ = cls.objects.get_or_create(
            workspace=workspace,
            name="All subscribers",
            defaults={"description": "Everyone who opted in."},
        )
        return obj


class CapturePage(WorkspaceOwned):
    """A generated lead-capture / bio-link landing page.

    Many can exist — each promotes a product + lead magnet and has its own public
    URL (/p/<slug>/). Niche-agnostic: all the copy comes from these fields.
    """

    title = models.CharField(max_length=200, help_text="Internal name for this page")
    slug = models.SlugField(unique=True, help_text="Public URL: /p/<slug>/")
    headline = models.CharField(max_length=200, help_text="The big promise at the top")
    subheadline = models.TextField(
        blank=True, help_text="Supporting line under the headline"
    )
    lead_magnet = models.CharField(
        max_length=200, help_text="The freebie visitors opt in for"
    )
    offer = models.ForeignKey(
        "offers.Offer",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="capture_pages",
        help_text="Product this page promotes (optional)",
    )
    email_list = models.ForeignKey(
        "leads.EmailList",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="capture_pages",
        help_text="New signups from this page join this list",
    )
    button_text = models.CharField(max_length=80, default="Send it to me →")
    success_message = models.CharField(
        max_length=300, blank=True, help_text="Shown after they opt in (optional)"
    )
    niche = models.CharField(max_length=200, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse("capture_page", args=[self.slug])


class Lead(WorkspaceOwned):
    """An email captured through the funnel."""

    class Stage(models.TextChoices):
        NEW = "new", "New"
        NURTURING = "nurturing", "Nurturing"
        CLICKED = "clicked", "Clicked product"
        CONVERTED = "converted", "Converted"

    email = models.EmailField()
    source_video = models.ForeignKey(
        "videos.Video",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="leads",
    )
    source_page = models.ForeignKey(
        "leads.CapturePage",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="leads",
        help_text="Which capture page converted them",
    )
    lead_magnet = models.CharField(
        max_length=200, blank=True, help_text="Freebie they opted in for"
    )
    stage = models.CharField(
        max_length=20, choices=Stage.choices, default=Stage.NEW
    )
    lists = models.ManyToManyField(
        "leads.EmailList", blank=True, related_name="leads"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        # Same email can be a lead in two different workspaces, but is unique
        # within one.
        constraints = [
            models.UniqueConstraint(
                fields=["workspace", "email"], name="uniq_lead_email_per_workspace"
            )
        ]

    def __str__(self):
        return self.email
