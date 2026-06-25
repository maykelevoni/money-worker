from django.db import models


class Offer(models.Model):
    """An affiliate product/tool we promote."""

    name = models.CharField(max_length=200)
    vendor = models.CharField(max_length=200, blank=True)
    affiliate_url = models.URLField(help_text="Your affiliate/referral link")
    landing_url = models.URLField(
        blank=True, help_text="Sales/landing page the funnel sends to"
    )
    commission = models.CharField(
        max_length=100, blank=True, help_text="e.g. '30% recurring'"
    )
    is_recurring = models.BooleanField(default=False)
    notes = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name
