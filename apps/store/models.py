import secrets

from django.contrib.auth.hashers import check_password, make_password
from django.db import models
from django.utils import timezone

from apps.accounts.models import WorkspaceOwned
from apps.offers.models import Offer


class Customer(WorkspaceOwned):
    """A buyer of the workspace's products — a separate identity from the
    creator's staff `accounts.Membership`. Never gets dashboard access.

    Keyed by the email they paid Stripe with. They set a password right after
    checkout (the payment proves it's them), then sign in with email + password.
    """

    email = models.EmailField()
    name = models.CharField(max_length=200, blank=True)
    password = models.CharField(max_length=255, blank=True)  # hashed; blank = not set yet
    stripe_customer_id = models.CharField(max_length=80, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def set_password(self, raw):
        self.password = make_password(raw)

    def check_password(self, raw):
        return bool(self.password) and check_password(raw, self.password)

    @property
    def has_password(self):
        return bool(self.password)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["workspace", "email"], name="uniq_customer_email_per_ws"
            )
        ]

    def __str__(self):
        return self.email

    @classmethod
    def get_or_create_for(cls, workspace, email, name="", stripe_customer_id=""):
        email = (email or "").strip().lower()
        obj, created = cls.objects.get_or_create(
            workspace=workspace,
            email=email,
            defaults={"name": name, "stripe_customer_id": stripe_customer_id},
        )
        # Backfill the Stripe id if we learn it later.
        if stripe_customer_id and not obj.stripe_customer_id:
            obj.stripe_customer_id = stripe_customer_id
            obj.save(update_fields=["stripe_customer_id"])
        return obj, created

    @property
    def active_entitlements(self):
        return self.entitlements.filter(status=Entitlement.Status.ACTIVE)


class Entitlement(WorkspaceOwned):
    """Grants one Customer access to one product. The single source of truth for
    "can this person see the product". A Stripe webhook flips the status.

    Access checks are per-product, so this stays valid when a product later
    grows course modules or a community — they all hang off the same grant.
    """

    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        CANCELED = "canceled", "Canceled"      # subscription ended / lapsed
        REFUNDED = "refunded", "Refunded"      # payment reversed

    customer = models.ForeignKey(
        Customer, on_delete=models.CASCADE, related_name="entitlements"
    )
    offer = models.ForeignKey(
        Offer, on_delete=models.CASCADE, related_name="entitlements"
    )
    access_type = models.CharField(
        max_length=20, choices=Offer.AccessType.choices, default=Offer.AccessType.ONE_TIME
    )
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.ACTIVE
    )
    # Stripe references — let the webhook match events back to this grant.
    stripe_checkout_session_id = models.CharField(max_length=120, blank=True)
    stripe_payment_intent_id = models.CharField(max_length=120, blank=True)
    stripe_subscription_id = models.CharField(max_length=120, blank=True)
    # For subscriptions: paid-through date. Access holds until then even on cancel.
    current_period_end = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["customer", "offer"], name="uniq_entitlement_per_product"
            )
        ]

    def __str__(self):
        return f"{self.customer.email} → {self.offer.name} ({self.status})"

    @property
    def grants_access(self):
        """Whether the buyer can currently open the product.

        Active always grants. A canceled subscription still grants until the
        paid period runs out (Stripe keeps access to period end)."""
        if self.status == self.Status.ACTIVE:
            return True
        if (
            self.status == self.Status.CANCELED
            and self.current_period_end
            and self.current_period_end > timezone.now()
        ):
            return True
        return False


class LoginToken(models.Model):
    """A single-use token for a Customer, used for password reset ("forgot
    password"). We store only a hash, so a leaked row can't be used. One-shot
    and short-lived."""

    customer = models.ForeignKey(
        Customer, on_delete=models.CASCADE, related_name="login_tokens"
    )
    token_hash = models.CharField(max_length=64, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    used_at = models.DateTimeField(null=True, blank=True)

    @staticmethod
    def _hash(raw):
        import hashlib

        return hashlib.sha256(raw.encode()).hexdigest()

    @classmethod
    def issue(cls, customer):
        """Create a token and return the raw secret (only shown once, emailed)."""
        raw = secrets.token_urlsafe(32)
        cls.objects.create(customer=customer, token_hash=cls._hash(raw))
        return raw

    @classmethod
    def consume(cls, raw, max_age_minutes=30):
        """Validate + burn a token, returning its Customer or None."""
        tok = cls.objects.filter(token_hash=cls._hash(raw), used_at__isnull=True).first()
        if tok is None:
            return None
        age = timezone.now() - tok.created_at
        if age.total_seconds() > max_age_minutes * 60:
            return None
        tok.used_at = timezone.now()
        tok.save(update_fields=["used_at"])
        return tok.customer
