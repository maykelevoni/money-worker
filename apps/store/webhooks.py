"""Stripe webhook processing — the only place access is granted or revoked.

Kept separate from the HTTP view so the branching is easy to read and test.
Every handler is idempotent: Stripe retries events, and replaying one must not
duplicate a grant or double-revoke.
"""
from apps.offers.models import Offer

from .models import Entitlement
from .services import access


def _offer_from_metadata(meta):
    key = (meta or {}).get("offer_key")
    if not key:
        return None
    return Offer.objects.filter(public_key=key).first()


def handle_checkout_completed(session):
    """A buyer finished paying — grant access and email them a magic link."""
    offer = _offer_from_metadata(session.get("metadata"))
    if offer is None:
        return
    email = (
        (session.get("customer_details") or {}).get("email")
        or session.get("customer_email")
        or ""
    )
    if not email:
        return
    name = (session.get("customer_details") or {}).get("name") or ""
    customer, _ent, _created = access.grant(
        offer,
        email,
        name=name,
        stripe_customer_id=session.get("customer") or "",
        session_id=session.get("id") or "",
        payment_intent_id=session.get("payment_intent") or "",
        subscription_id=session.get("subscription") or "",
    )
    access.send_purchase_confirmation(customer, offer)


def handle_subscription_updated(sub):
    """Keep a subscription entitlement's status + paid-through date in sync."""
    ent = Entitlement.objects.filter(stripe_subscription_id=sub.get("id")).first()
    if ent is None:
        return
    ent.current_period_end = access._ts_to_dt(sub.get("current_period_end"))
    status = sub.get("status")
    if status in ("active", "trialing"):
        ent.status = Entitlement.Status.ACTIVE
    elif status in ("canceled", "unpaid", "incomplete_expired", "past_due"):
        ent.status = Entitlement.Status.CANCELED
    ent.save(update_fields=["status", "current_period_end", "updated_at"])


def handle_subscription_deleted(sub):
    ent = Entitlement.objects.filter(stripe_subscription_id=sub.get("id")).first()
    if ent is not None:
        access.revoke(ent, Entitlement.Status.CANCELED)


def handle_charge_refunded(charge):
    """A one-time payment was refunded — pull access."""
    pi = charge.get("payment_intent")
    if not pi:
        return
    ent = Entitlement.objects.filter(stripe_payment_intent_id=pi).first()
    if ent is not None:
        access.revoke(ent, Entitlement.Status.REFUNDED)


DISPATCH = {
    "checkout.session.completed": handle_checkout_completed,
    "customer.subscription.updated": handle_subscription_updated,
    "customer.subscription.deleted": handle_subscription_deleted,
    "charge.refunded": handle_charge_refunded,
}


def process_event(event):
    """Route a verified Stripe event object to its handler (no-op if unknown)."""
    handler = DISPATCH.get(event.get("type"))
    if handler:
        handler(event["data"]["object"])
