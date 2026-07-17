"""Thin wrapper over the Stripe SDK.

Stripe holds the money and hosts checkout; this module only creates the objects
we need (a Product + Price per sellable Offer) and a Checkout Session per buy.
Access is granted later by the webhook (see apps.store.webhooks), never here.
"""
import stripe
from django.conf import settings

from apps.offers.models import Offer


class NotConfigured(Exception):
    pass


def is_configured() -> bool:
    return bool(settings.STRIPE_SECRET_KEY)


def _client():
    if not is_configured():
        raise NotConfigured("Set STRIPE_SECRET_KEY in your .env")
    stripe.api_key = settings.STRIPE_SECRET_KEY
    return stripe


def ensure_price(offer: Offer) -> str:
    """Return the Stripe Price id for this product, creating the Product/Price
    the first time. Cached on the Offer so we don't recreate on every checkout.

    If the amount or billing cadence changed, we create a fresh Price (Stripe
    prices are immutable) and repoint the Offer at it."""
    client = _client()

    if not offer.stripe_product_id:
        product = client.Product.create(
            name=offer.name,
            metadata={"offer_key": offer.public_key, "workspace": str(offer.workspace_id)},
        )
        offer.stripe_product_id = product.id
        offer.stripe_price_id = ""  # force a new price for the new product
        offer.save(update_fields=["stripe_product_id", "stripe_price_id"])

    if offer.stripe_price_id:
        # Verify the cached price still matches the current amount/cadence.
        try:
            price = client.Price.retrieve(offer.stripe_price_id)
            recurring = bool(price.get("recurring"))
            if (
                price["unit_amount"] == offer.price_cents
                and price["currency"] == offer.currency
                and recurring == offer.is_subscription
            ):
                return offer.stripe_price_id
        except stripe.error.StripeError:
            pass  # fall through and recreate

    params = {
        "product": offer.stripe_product_id,
        "unit_amount": offer.price_cents,
        "currency": offer.currency,
    }
    if offer.is_subscription:
        params["recurring"] = {"interval": "month"}
    price = client.Price.create(**params)
    offer.stripe_price_id = price.id
    offer.save(update_fields=["stripe_price_id"])
    return price.id


def verify_paid_session(session_id: str):
    """Confirm a Checkout Session was actually paid, returning the buyer's
    details. This is how the success page proves it's really them before letting
    them set a password — never trust the browser, ask Stripe.

    Returns a dict {email, name, customer_id, offer} or None if not paid/invalid.
    """
    if not session_id:
        return None
    client = _client()
    try:
        s = client.checkout.Session.retrieve(session_id)
    except stripe.error.StripeError:
        return None
    paid = s.get("payment_status") == "paid" or s.get("status") == "complete"
    if not paid:
        return None
    details = s.get("customer_details") or {}
    key = (s.get("metadata") or {}).get("offer_key")
    return {
        "email": (details.get("email") or s.get("customer_email") or "").strip().lower(),
        "name": details.get("name") or "",
        "customer_id": s.get("customer") or "",
        "offer": Offer.objects.filter(public_key=key).first() if key else None,
    }


def create_checkout_session(offer: Offer, success_url: str, cancel_url: str,
                            customer_email: str | None = None) -> str:
    """Create a hosted Checkout Session and return its URL."""
    client = _client()
    price_id = ensure_price(offer)
    mode = "subscription" if offer.is_subscription else "payment"

    params = {
        "mode": mode,
        "line_items": [{"price": price_id, "quantity": 1}],
        "success_url": success_url,
        "cancel_url": cancel_url,
        # Metadata rides through to the webhook so we know what was bought.
        "metadata": {"offer_key": offer.public_key, "workspace": str(offer.workspace_id)},
    }
    if customer_email:
        params["customer_email"] = customer_email
    if mode == "subscription":
        # Mirror the metadata onto the subscription for later lifecycle events.
        params["subscription_data"] = {
            "metadata": {"offer_key": offer.public_key, "workspace": str(offer.workspace_id)}
        }

    session = client.checkout.Session.create(**params)
    return session.url
