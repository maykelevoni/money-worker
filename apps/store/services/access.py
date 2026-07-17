"""Granting and revoking access to products, plus the emails that go with it.

This is the bridge between "Stripe says they paid" and "they can open the
product". Called from the webhook; kept out of the view so it can be reused
(e.g. a manual grant from the admin later).
"""
from datetime import datetime, timezone as _tz

from django.conf import settings
from django.urls import reverse

from apps.leads.services import email as mailer
from apps.offers.models import Offer

from ..models import Customer, Entitlement, LoginToken


def _abs(path: str) -> str:
    return f"{settings.APP_BASE_URL.rstrip('/')}{path}"


def _ts_to_dt(ts):
    return datetime.fromtimestamp(ts, tz=_tz.utc) if ts else None


def grant(offer: Offer, email: str, *, name="", stripe_customer_id="",
          session_id="", payment_intent_id="", subscription_id="", current_period_end=None):
    """Create/refresh the Customer + Entitlement for a completed purchase.

    Returns (customer, entitlement, created). Idempotent: replaying the same
    webhook re-activates the same grant rather than duplicating it."""
    customer, _ = Customer.get_or_create_for(
        offer.workspace, email, name=name, stripe_customer_id=stripe_customer_id
    )
    ent, created = Entitlement.objects.get_or_create(
        workspace=offer.workspace,
        customer=customer,
        offer=offer,
        defaults={
            "access_type": offer.access_type,
            "status": Entitlement.Status.ACTIVE,
            "stripe_checkout_session_id": session_id,
            "stripe_payment_intent_id": payment_intent_id,
            "stripe_subscription_id": subscription_id,
            "current_period_end": _ts_to_dt(current_period_end),
        },
    )
    if not created:
        ent.status = Entitlement.Status.ACTIVE
        ent.access_type = offer.access_type
        if session_id:
            ent.stripe_checkout_session_id = session_id
        if payment_intent_id:
            ent.stripe_payment_intent_id = payment_intent_id
        if subscription_id:
            ent.stripe_subscription_id = subscription_id
        if current_period_end:
            ent.current_period_end = _ts_to_dt(current_period_end)
        ent.save()
    return customer, ent, created


def send_purchase_confirmation(customer: Customer, offer: Offer):
    """Receipt email — confirms the purchase and points to sign-in. No login
    link: the buyer sets a password on the checkout success page."""
    if not mailer.is_configured():
        return
    login_url = _abs(reverse("store:login"))
    html = (
        f'<div style="font-family:Arial,Helvetica,sans-serif;line-height:1.6;max-width:520px">'
        f"<h2>Thanks for your purchase.</h2>"
        f"<p>Your access to <strong>{offer.name}</strong> is ready. Sign in any time "
        f"with your email and password.</p>"
        f'<p><a href="{login_url}" style="display:inline-block;padding:12px 22px;'
        f'background:#ff7e2e;color:#fff;text-decoration:none;border-radius:8px;'
        f'font-weight:600">Go to my products</a></p>'
        f'<p style="color:#777;font-size:13px">Didn\'t set a password yet? Use '
        f'"Forgot password" on the sign-in page to set one.</p>'
        f"</div>"
    )
    mailer.send_email(to=customer.email, subject=f"Your purchase: {offer.name}", html=html)


def send_reset_link(customer: Customer):
    """Email a password-reset link (recovery only)."""
    if not mailer.is_configured():
        return
    raw = LoginToken.issue(customer)
    link = _abs(reverse("store:reset_password", args=[raw]))
    html = (
        f'<div style="font-family:Arial,Helvetica,sans-serif;line-height:1.6;max-width:520px">'
        f"<h2>Set a new password</h2>"
        f"<p>Click below to choose a new password for your products.</p>"
        f'<p><a href="{link}" style="display:inline-block;padding:12px 22px;'
        f'background:#ff7e2e;color:#fff;text-decoration:none;border-radius:8px;'
        f'font-weight:600">Set my password</a></p>'
        f'<p style="color:#777;font-size:13px">This link works for 30 minutes. '
        f"If you didn't ask for this, ignore it.</p>"
        f"</div>"
    )
    mailer.send_email(to=customer.email, subject="Set your password", html=html)


def revoke(entitlement: Entitlement, status: str):
    """Mark an entitlement canceled/refunded (called on refund/cancel webhooks)."""
    entitlement.status = status
    entitlement.save(update_fields=["status", "updated_at"])
