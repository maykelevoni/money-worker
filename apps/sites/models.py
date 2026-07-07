from django.conf import settings
from django.db import models
from django.utils.text import slugify

from apps.accounts.models import WorkspaceOwned


class Website(WorkspaceOwned):
    """One SEO website — a few static Pages plus a blog (content.Post articles).

    Native multi-site: many Websites live in one app. A site is reachable at
    `<subdomain>.<SITE_HOST>` (default address) or its own `custom_domain` once
    connected. In Phase 1a the app renders sites directly; Phase 1b static-exports
    them to a CDN using the same templates.
    """

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        PUBLISHED = "published", "Published"

    class Platform(models.TextChoices):
        NATIVE = "native", "Native (this app)"

    class Theme(models.TextChoices):
        MINIMAL = "minimal", "Minimal"
        BOLD = "bold", "Bold"
        EDITORIAL = "editorial", "Editorial"
        WARM = "warm", "Warm"
        TECH = "tech", "Tech"

    name = models.CharField(max_length=200)
    theme = models.CharField(
        max_length=20, choices=Theme.choices, default=Theme.MINIMAL,
        help_text="Visual style — fonts, layout and section styling",
    )
    subdomain = models.SlugField(
        unique=True, help_text="Default address: <subdomain>.<app host>"
    )
    custom_domain = models.CharField(
        max_length=253, blank=True, null=True, unique=True,
        help_text="e.g. sleeptips.co — connected in Phase 1b",
    )
    platform = models.CharField(
        max_length=20, choices=Platform.choices, default=Platform.NATIVE
    )
    tagline = models.CharField(max_length=300, blank=True)

    # Branding
    logo = models.ImageField(upload_to="sites/logos/", blank=True)
    accent_color = models.CharField(max_length=9, default="#ff7e2e")

    # SEO defaults — inherited by pages/posts that don't override them.
    seo_title_suffix = models.CharField(
        max_length=120, blank=True, help_text="Appended to page titles, e.g. ' · Sleep Tips'"
    )
    seo_description = models.TextField(blank=True)
    og_image = models.ImageField(upload_to="sites/og/", blank=True)

    status = models.CharField(
        max_length=12, choices=Status.choices, default=Status.DRAFT
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    @property
    def is_published(self):
        return self.status == self.Status.PUBLISHED

    @property
    def host(self):
        """The primary hostname this site answers on."""
        if self.custom_domain:
            return self.custom_domain
        return f"{self.subdomain}.{settings.SITE_HOST}"

    @property
    def public_url(self):
        scheme = "https" if not settings.DEBUG else "http"
        return f"{scheme}://{self.host}/"

    @property
    def preview_url(self):
        """In-app preview — works without DNS (used in dev/verification)."""
        from django.urls import reverse

        return reverse("sites:preview_home", args=[self.pk])

    def title_for(self, page_title):
        return f"{page_title}{self.seo_title_suffix}" if page_title else self.name


class Page(WorkspaceOwned):
    """A static page on a Website (home, about, a landing page…)."""

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        PUBLISHED = "published", "Published"

    website = models.ForeignKey(
        Website, on_delete=models.CASCADE, related_name="pages"
    )
    title = models.CharField(max_length=200)
    slug = models.SlugField(
        blank=True, help_text="URL on the site; blank = home page"
    )
    body = models.TextField(blank=True, help_text="Markdown")
    meta_title = models.CharField(
        max_length=200, blank=True, help_text="Overrides the site default title"
    )
    meta_description = models.TextField(blank=True)
    is_home = models.BooleanField(default=False)
    nav_order = models.PositiveIntegerField(default=0)
    status = models.CharField(
        max_length=12, choices=Status.choices, default=Status.PUBLISHED
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["nav_order", "title"]
        constraints = [
            models.UniqueConstraint(
                fields=["website", "slug"], name="uniq_page_slug_per_site"
            )
        ]

    def __str__(self):
        return f"{self.website.name} / {self.title}"

    def save(self, *args, **kwargs):
        if self.is_home:
            self.slug = ""
        elif not self.slug:
            self.slug = slugify(self.title)
        super().save(*args, **kwargs)

    @property
    def path(self):
        return "/" if self.is_home else f"/{self.slug}/"

    @property
    def is_published(self):
        return self.status == self.Status.PUBLISHED


# Sections a page can be built from, and the starter content for each kind.
SECTION_DEFAULTS = {
    "hero": {
        "headline": "Your big headline goes here",
        "subtext": "One supporting sentence that says what this is and who it's for.",
        "button_text": "Get started",
        "button_url": "",
    },
    "features": {
        "items": [
            {"title": "First benefit", "body": "Say why it matters in a line."},
            {"title": "Second benefit", "body": "Keep each one short and concrete."},
            {"title": "Third benefit", "body": "Three is the sweet spot."},
        ]
    },
    "text": {"body": "Write your content here in **Markdown**."},
    "cta": {
        "headline": "Ready to get started?",
        "button_text": "Join now",
        "button_url": "",
    },
    "faq": {
        "items": [
            {"q": "A common question?", "a": "A clear, short answer."},
        ]
    },
    "optin": {
        "headline": "Get the free guide",
        "subtext": "Drop your email and I'll send it straight over.",
        "lead_magnet": "Free guide",
        "button_text": "Send it to me →",
        "success_message": "Check your inbox — it's on the way!",
    },
    "testimonial": {
        "quote": "This completely changed how I approach it. Wish I'd found it sooner.",
        "author": "Happy Customer",
        "role": "",
    },
    "stats": {
        "items": [
            {"value": "10k+", "label": "Readers"},
            {"value": "4.9★", "label": "Rating"},
            {"value": "24h", "label": "Support"},
        ]
    },
    "image": {"caption": ""},
}

# Kinds that a home page must always keep at least one of.
MANDATORY_KINDS = {"hero", "cta"}


class Section(WorkspaceOwned):
    """One ordered content block on a Page. `data` holds per-kind fields."""

    class Kind(models.TextChoices):
        HERO = "hero", "Hero"
        FEATURES = "features", "Features"
        TEXT = "text", "Text"
        CTA = "cta", "Call to action"
        FAQ = "faq", "FAQ"
        OPTIN = "optin", "Email capture"
        TESTIMONIAL = "testimonial", "Testimonial"
        STATS = "stats", "Stats / social proof"
        IMAGE = "image", "Image"

    page = models.ForeignKey(
        Page, on_delete=models.CASCADE, related_name="sections"
    )
    kind = models.CharField(max_length=20, choices=Kind.choices)
    order = models.PositiveIntegerField(default=0)
    data = models.JSONField(default=dict, blank=True)
    image = models.ImageField(upload_to="sites/sections/", blank=True)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return f"{self.page} · {self.get_kind_display()}"

    @property
    def template(self):
        return f"sites/public/sections/{self.kind}.html"

    @property
    def is_mandatory(self):
        return self.kind in MANDATORY_KINDS

    @classmethod
    def default_data(cls, kind):
        import copy

        return copy.deepcopy(SECTION_DEFAULTS.get(kind, {}))
