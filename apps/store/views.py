from django.contrib import messages
from django.http import FileResponse, HttpResponse, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from apps.offers.models import Offer, ProductContent

from . import webhooks
from .auth import current_customer, customer_required, login_customer, logout_customer
from .models import Customer, Entitlement, LoginToken
from .services import stripe_gateway


# ---------------------------------------------------------------------------
# Public checkout — no login needed; Stripe collects the email.
# ---------------------------------------------------------------------------
def buy(request, offer_key):
    """Send a buyer to Stripe Checkout for a sellable product."""
    offer = get_object_or_404(Offer, public_key=offer_key)
    if not offer.is_sellable:
        return HttpResponseBadRequest("This product isn't available for purchase.")
    if not stripe_gateway.is_configured():
        return HttpResponse(
            "Payments aren't set up yet. Add STRIPE_SECRET_KEY to enable checkout.",
            status=503,
        )
    success = request.build_absolute_uri(reverse("store:checkout_success")) + "?session_id={CHECKOUT_SESSION_ID}"
    cancel = request.build_absolute_uri(reverse("store:checkout_cancel"))
    try:
        url = stripe_gateway.create_checkout_session(offer, success, cancel)
    except Exception as exc:  # surface config/Stripe errors instead of a 500
        return HttpResponse(f"Could not start checkout: {exc}", status=502)
    return redirect(url)


def checkout_success(request):
    """Back from Stripe. Verify the session was paid, then let the buyer set a
    password on the spot (no email needed — the payment proves it's them)."""
    session_id = request.GET.get("session_id", "")
    info = None
    if session_id and stripe_gateway.is_configured():
        info = stripe_gateway.verify_paid_session(session_id)

    if info and info["email"]:
        customer, _ = Customer.get_or_create_for(
            info["offer"].workspace if info["offer"] else _fallback_workspace(),
            info["email"], name=info["name"], stripe_customer_id=info["customer_id"],
        )
        if customer.has_password:
            messages.info(request, "You already have an account — just sign in below.")
            return redirect("store:login")
        return render(request, "store/set_password.html",
                      {"email": customer.email, "session_id": session_id})

    # No verifiable session (e.g. Stripe not configured yet) — generic thanks.
    return render(request, "store/checkout_success.html")


def _fallback_workspace():
    from apps.accounts.models import Workspace
    return Workspace.objects.first()


@require_POST
def set_password(request):
    """Set the buyer's password, re-verifying the paid session server-side so
    nobody can claim an account they didn't pay for."""
    session_id = request.POST.get("session_id", "")
    pw = request.POST.get("password", "")
    info = stripe_gateway.verify_paid_session(session_id) if stripe_gateway.is_configured() else None
    if not info or not info["email"]:
        messages.error(request, "We couldn't verify that purchase. Please sign in or reset your password.")
        return redirect("store:login")
    if len(pw) < 8:
        messages.error(request, "Use at least 8 characters.")
        return render(request, "store/set_password.html",
                      {"email": info["email"], "session_id": session_id})
    customer, _ = Customer.get_or_create_for(
        info["offer"].workspace if info["offer"] else _fallback_workspace(), info["email"]
    )
    customer.set_password(pw)
    customer.save(update_fields=["password"])
    login_customer(request, customer)
    return redirect("store:portal")


def forgot_password(request):
    """Email a reset link (recovery only — not the normal way to sign in)."""
    if request.method == "POST":
        email = request.POST.get("email", "").strip().lower()
        from .services.access import send_reset_link
        for customer in Customer.objects.filter(email=email):
            send_reset_link(customer)
        messages.success(request, "If that email has an account, we sent a reset link.")
        return redirect("store:login")
    return render(request, "store/forgot_password.html")


def reset_password(request, token):
    # GET carries the token into the form; the token is only burned on POST.
    if request.method == "POST":
        raw = request.POST.get("token", "")
        customer = LoginToken.consume(raw)
        pw = request.POST.get("password", "")
        if customer is None:
            messages.error(request, "That reset link expired. Request a new one.")
            return redirect("store:forgot_password")
        if len(pw) < 8:
            messages.error(request, "Use at least 8 characters.")
            return render(request, "store/reset_password.html", {"token": raw})
        customer.set_password(pw)
        customer.save(update_fields=["password"])
        login_customer(request, customer)
        return redirect("store:portal")
    # GET: don't consume yet — just show the form carrying the token.
    return render(request, "store/reset_password.html", {"token": token})


def checkout_cancel(request):
    return render(request, "store/checkout_cancel.html")


# ---------------------------------------------------------------------------
# Stripe webhook — the only place access is granted/revoked.
# ---------------------------------------------------------------------------
@csrf_exempt
@require_POST
def stripe_webhook(request):
    import stripe
    from django.conf import settings

    payload = request.body
    sig = request.META.get("HTTP_STRIPE_SIGNATURE", "")
    secret = settings.STRIPE_WEBHOOK_SECRET
    try:
        if secret:
            event = stripe.Webhook.construct_event(payload, sig, secret)
        else:
            # No secret configured (local dev) — parse without verifying.
            import json

            event = json.loads(payload or "{}")
    except (ValueError, stripe.error.SignatureVerificationError):
        return HttpResponse(status=400)

    try:
        webhooks.process_event(event)
    except Exception:
        # Ack anyway if we can't process; Stripe retries on 5xx and we don't
        # want an unrelated bug to wedge the whole webhook.
        return HttpResponse(status=200)
    return HttpResponse(status=200)


# ---------------------------------------------------------------------------
# Member area — email + password login + gated product content.
# ---------------------------------------------------------------------------
def login(request):
    """Email + password sign-in for returning buyers."""
    if current_customer(request):
        return redirect("store:portal")
    if request.method == "POST":
        email = request.POST.get("email", "").strip().lower()
        pw = request.POST.get("password", "")
        for customer in Customer.objects.filter(email=email):
            if customer.check_password(pw):
                login_customer(request, customer)
                return redirect("store:portal")
        messages.error(request, "Wrong email or password. If you just bought, set your password from the link on your receipt.")
        return redirect("store:login")
    return render(request, "store/login.html")


def logout(request):
    logout_customer(request)
    messages.info(request, "Signed out.")
    return redirect("store:login")


@customer_required
def portal(request):
    """The buyer's home — every product they have access to."""
    ents = (
        Entitlement.objects.filter(customer=request.customer)
        .select_related("offer")
    )
    products = [e.offer for e in ents if e.grants_access]
    return render(request, "store/portal.html", {"products": products, "customer": request.customer})


@customer_required
def product(request, offer_key):
    offer = get_object_or_404(Offer, public_key=offer_key)
    ent = Entitlement.objects.filter(customer=request.customer, offer=offer).first()
    if ent is None or not ent.grants_access:
        messages.error(request, "You don't have access to that product.")
        return redirect("store:portal")
    contents = offer.contents.all()
    return render(
        request, "store/product.html",
        {"offer": offer, "contents": contents, "entitlement": ent},
    )


@customer_required
def download(request, content_id):
    """Stream a product file — only if the buyer's entitlement is live."""
    content = get_object_or_404(ProductContent, pk=content_id)
    ent = Entitlement.objects.filter(
        customer=request.customer, offer=content.offer
    ).first()
    if ent is None or not ent.grants_access:
        return HttpResponse("Not authorized.", status=403)
    if not content.file:
        return HttpResponse("No file on this item.", status=404)
    return FileResponse(content.file.open("rb"), as_attachment=True,
                        filename=content.file.name.rsplit("/", 1)[-1])
