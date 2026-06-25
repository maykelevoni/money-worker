from django.db import models


class Offer(models.Model):
    """A product the funnel promotes — an affiliate product or Mayke's own.

    Kept as `Offer` internally (FKs from videos/leads point here) but presented
    as a "Product" in the UI.
    """

    class Kind(models.TextChoices):
        AFFILIATE = "affiliate", "Affiliate product"
        OWN = "own", "My own product"

    name = models.CharField(max_length=200)
    kind = models.CharField(
        max_length=20, choices=Kind.choices, default=Kind.AFFILIATE
    )
    vendor = models.CharField(max_length=200, blank=True)

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

    def __str__(self):
        return self.name

    @property
    def primary_url(self):
        """The link the funnel should send buyers to for this product."""
        if self.kind == self.Kind.OWN:
            return self.checkout_url or self.landing_url
        return self.affiliate_url or self.landing_url
