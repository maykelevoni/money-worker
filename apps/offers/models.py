import secrets

from django.db import models

from apps.accounts.models import WorkspaceOwned


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


class ProductContent(WorkspaceOwned):
    """One piece of what a buyer unlocks after purchase — a download or a
    written lesson. Gated behind an active Entitlement (apps.store).

    Kept deliberately flat for Phase 1 (an ordered list per product). A later
    "courses" phase can group these under modules without reshaping access:
    entitlement checks are per-product, not per-item.
    """

    offer = models.ForeignKey(
        Offer, on_delete=models.CASCADE, related_name="contents"
    )
    title = models.CharField(max_length=200)
    order = models.PositiveIntegerField(default=0)
    body = models.TextField(
        blank=True, help_text="Written content shown in the members area (Markdown)"
    )
    file = models.FileField(
        upload_to="products/", blank=True,
        help_text="Downloadable file delivered to buyers",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return f"{self.offer.name} · {self.title}"
