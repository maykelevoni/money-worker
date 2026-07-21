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

    class Layout(models.TextChoices):
        CAPTURE = "capture", "Email capture (opt-in for a freebie)"
        SALES = "sales", "Sales page (sell a product)"
        BIO = "bio", "Link hub (bio link for your videos)"

    layout = models.CharField(
        max_length=12, choices=Layout.choices, default=Layout.CAPTURE,
        help_text="What this page is for — picks the public design",
    )
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
        help_text="Paid product this page promotes / sells (optional)",
    )
    freebie = models.ForeignKey(
        "offers.Offer",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="freebie_captures",
        help_text="The freebie (lead magnet) visitors opt in for — delivered on its download page",
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
    # Bio/link-hub: the influencer whose face + name front the hub. Preferred over
    # `avatar` — keeps the page in sync if the influencer's image is regenerated.
    influencer = models.ForeignKey(
        "videos.Avatar",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="bio_pages",
        help_text="Bio pages: the influencer who fronts this link hub",
    )
    # Fallback face for anyone without an influencer yet (or a custom upload).
    avatar = models.ImageField(upload_to="capture/avatars/", blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse("capture_page", args=[self.slug])

    @property
    def public_template(self):
        return {
            self.Layout.SALES: "leads/sales.html",
            self.Layout.BIO: "leads/bio.html",
        }.get(self.layout, "leads/page.html")

    @property
    def face(self):
        """The image shown at the top of a bio hub: the influencer's, else the
        uploaded fallback. Returns a file/ImageField-like or None."""
        if self.influencer_id and getattr(self.influencer, "image", None):
            return self.influencer.image
        return self.avatar or None


class PageLink(WorkspaceOwned):
    """One button on a bio/link-hub CapturePage — where the creator's video
    traffic can go (socials, other pages, an affiliate link)."""

    page = models.ForeignKey(
        CapturePage, on_delete=models.CASCADE, related_name="links"
    )
    label = models.CharField(max_length=120)
    url = models.URLField()
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return f"{self.page.title} · {self.label}"


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
