import secrets

from django.db import models

from apps.accounts.models import WorkspaceOwned


def _product_upload_to(instance, filename):
    """Store paid files under an unguessable random prefix. Downloads are gated
    by the entitlement-checked view; the random key means the object's direct
    storage URL can't be guessed/enumerated even on a public bucket."""
    return f"products/{secrets.token_urlsafe(12)}/{filename}"


class Offer(WorkspaceOwned):
    """A product the funnel promotes — an affiliate product or Mayke's own.

    Kept as `Offer` internally (FKs from videos/leads point here) but presented
    as a "Product" in the UI.
    """

    class Kind(models.TextChoices):
        AFFILIATE = "affiliate", "Affiliate product"
        OWN = "own", "My own product"

    class AccessType(models.TextChoices):
        # "none" keeps the legacy behaviour: the funnel just links out to
        # checkout_url/affiliate_url. one_time / subscription switch the product
        # to native selling — Stripe takes the money, we grant access (apps.store).
        NONE = "none", "Link out only"
        ONE_TIME = "one_time", "One-time purchase (lifetime access)"
        SUBSCRIPTION = "subscription", "Subscription (recurring access)"

    name = models.CharField(max_length=200)
    kind = models.CharField(
        max_length=20, choices=Kind.choices, default=Kind.AFFILIATE
    )
    vendor = models.CharField(max_length=200, blank=True)
    image = models.ImageField(
        upload_to="offers/", blank=True, help_text="Product image shown in blog CTAs"
    )

    # Affiliate products
    affiliate_url = models.URLField(blank=True, help_text="Your affiliate/referral link")
    commission = models.CharField(
        max_length=100, blank=True, help_text="e.g. '30% recurring'"
    )
    is_recurring = models.BooleanField(default=False)

    # Your own products
    price = models.CharField(
        max_length=50, blank=True, help_text="e.g. '$29' or '$29/mo'"
    )
    checkout_url = models.URLField(blank=True, help_text="Where buyers pay")

    landing_url = models.URLField(
        blank=True, help_text="Sales/landing page the funnel sends to"
    )
    notes = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    # --- Native selling (Stripe takes the money, we grant access) ----------
    access_type = models.CharField(
        max_length=20, choices=AccessType.choices, default=AccessType.NONE,
        help_text="Native selling: how buyers get access once they pay via Stripe",
    )
    price_cents = models.PositiveIntegerField(
        null=True, blank=True,
        help_text="Native price in the smallest currency unit, e.g. 2900 = $29.00",
    )
    currency = models.CharField(max_length=3, default="usd")
    # Members-only discussion space for buyers of this product.
    community_enabled = models.BooleanField(
        default=False, help_text="Give buyers a members-only discussion space",
    )
    # Public, unguessable key for the /buy/<key>/ checkout link.
    public_key = models.CharField(max_length=40, unique=True, blank=True)
    # Cached Stripe object ids so we don't recreate them on every checkout.
    stripe_product_id = models.CharField(max_length=80, blank=True)
    stripe_price_id = models.CharField(max_length=80, blank=True)

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.public_key:
            self.public_key = secrets.token_urlsafe(24)
        super().save(*args, **kwargs)

    @property
    def is_sellable(self):
        """True when this product is set up to be sold natively via Stripe."""
        return (
            self.kind == self.Kind.OWN
            and self.access_type != self.AccessType.NONE
            and bool(self.price_cents)
        )

    @property
    def is_subscription(self):
        return self.access_type == self.AccessType.SUBSCRIPTION

    @property
    def price_display(self):
        """Human price from the structured amount, falling back to the free-text price."""
        if self.price_cents:
            amount = self.price_cents / 100
            body = f"${amount:,.0f}" if amount == int(amount) else f"${amount:,.2f}"
            return f"{body}/mo" if self.is_subscription else body
        return self.price

    @property
    def primary_url(self):
        """The link the funnel should send buyers to for this product."""
        if self.kind == self.Kind.OWN:
            return self.checkout_url or self.landing_url
        return self.affiliate_url or self.landing_url


class Module(WorkspaceOwned):
    """A section of a course — groups lessons (ProductContent) under a heading.
    Optional: a product can still be a flat list of lessons with no modules."""

    offer = models.ForeignKey(
        Offer, on_delete=models.CASCADE, related_name="modules"
    )
    title = models.CharField(max_length=200)
    order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return f"{self.offer.name} · {self.title}"


class ProductContent(WorkspaceOwned):
    """One lesson a buyer unlocks after purchase — a download and/or written
    content. Gated behind an active Entitlement (apps.store).

    Optionally grouped under a Module (course structure) and optionally dripped
    (unlocks N days after purchase). Access is still per-product: the entitlement
    grants the whole thing; module/drip only shape *when* each lesson appears.
    """

    offer = models.ForeignKey(
        Offer, on_delete=models.CASCADE, related_name="contents"
    )
    module = models.ForeignKey(
        Module, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="lessons", help_text="Course section this lesson belongs to",
    )
    title = models.CharField(max_length=200)
    order = models.PositiveIntegerField(default=0)
    body = models.TextField(
        blank=True, help_text="Written content shown in the members area (Markdown)"
    )
    file = models.FileField(
        upload_to=_product_upload_to, blank=True,
        help_text="Downloadable file delivered to buyers",
    )
    video_url = models.URLField(
        blank=True,
        help_text="YouTube, Vimeo or Loom link — plays inline in the members area",
    )
    drip_days = models.PositiveIntegerField(
        default=0, help_text="Days after purchase before this unlocks (0 = right away)",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return f"{self.offer.name} · {self.title}"

    @property
    def video_embed(self):
        """An embeddable iframe src for known hosts, or '' if we don't recognise
        the URL (we only embed trusted video hosts, never an arbitrary iframe)."""
        import re

        u = (self.video_url or "").strip()
        if not u:
            return ""
        m = re.search(r"(?:youtube\.com/(?:watch\?v=|shorts/|embed/)|youtu\.be/)([\w-]{6,})", u)
        if m:
            return f"https://www.youtube.com/embed/{m.group(1)}"
        m = re.search(r"vimeo\.com/(?:video/)?(\d+)", u)
        if m:
            return f"https://player.vimeo.com/video/{m.group(1)}"
        m = re.search(r"loom\.com/(?:share|embed)/([\w-]+)", u)
        if m:
            return f"https://www.loom.com/embed/{m.group(1)}"
        return ""

    def unlock_date(self, since):
        """When this lesson becomes available, given a purchase/entitlement date."""
        from datetime import timedelta

        return since + timedelta(days=self.drip_days)

    def is_unlocked(self, since):
        from django.utils import timezone

        return self.drip_days == 0 or timezone.now() >= self.unlock_date(since)
