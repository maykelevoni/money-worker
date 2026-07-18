from django.contrib import messages
from django.contrib.auth.decorators import login_required
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
# Creator dashboard — who bought, and how much money.
# ---------------------------------------------------------------------------
@login_required
def customers_dashboard(request):
    ws = request.workspace
    ents = list(
        Entitlement.objects.for_workspace(ws).select_related("offer", "customer")
    )
    customers = (
        Customer.objects.for_workspace(ws)
        .prefetch_related("entitlements__offer")
        .order_by("-created_at")
    )

    one_time_cents = sum(
        e.offer.price_cents or 0 for e in ents
        if e.access_type == Offer.AccessType.ONE_TIME and e.status == Entitlement.Status.ACTIVE
    )
    mrr_cents = sum(
        e.offer.price_cents or 0 for e in ents
        if e.access_type == Offer.AccessType.SUBSCRIPTION and e.status == Entitlement.Status.ACTIVE
    )
    active_access = sum(1 for e in ents if e.grants_access)

    rows = []
    for c in customers:
        c_ents = list(c.entitlements.all())
        rows.append({
            "customer": c,
            "products": [e.offer.name for e in c_ents if e.grants_access],
            "has_access": any(e.grants_access for e in c_ents),
            "any_refunded": any(e.status == Entitlement.Status.REFUNDED for e in c_ents),
        })

    return render(request, "store/customers.html", {
        "rows": rows,
        "customer_count": customers.count(),
        "active_access": active_access,
        "one_time_revenue": one_time_cents / 100,
        "mrr": mrr_cents / 100,
        "sales_count": len(ents),
    })


@login_required
def offer_community(request, pk):
    """Creator's view of a product community: post announcements, moderate."""
    from .models import Post

    offer = get_object_or_404(Offer, pk=pk, workspace=request.workspace)
    if request.method == "POST":
        body = request.POST.get("body", "").strip()
        if body:
            Post.objects.create(
                workspace=request.workspace, offer=offer, is_creator=True, body=body
            )
        return redirect("store:offer_community", pk=pk)

    posts = list(offer.posts.select_related("author").prefetch_related("comments__author"))
    for p in posts:  # staff can moderate everything
        p.deletable = True
        for c in p.comments.all():
            c.deletable = True
    return render(request, "store/offer_community.html", {"offer": offer, "posts": posts})


@login_required
@require_POST
def offer_community_comment(request, pk, post_id):
    from .models import Comment, Post

    post = get_object_or_404(Post, pk=post_id, workspace=request.workspace)
    body = request.POST.get("body", "").strip()
    if body:
        Comment.objects.create(
            workspace=request.workspace, post=post, is_creator=True, body=body
        )
    return redirect("store:offer_community", pk=pk)


@login_required
@require_POST
def offer_community_post_delete(request, pk, post_id):
    from .models import Post

    get_object_or_404(Post, pk=post_id, workspace=request.workspace).delete()
    return redirect("store:offer_community", pk=pk)


@login_required
@require_POST
def offer_community_comment_delete(request, pk, comment_id):
    from .models import Comment

    get_object_or_404(Comment, pk=comment_id, workspace=request.workspace).delete()
    return redirect("store:offer_community", pk=pk)


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

    import json
    import logging

    payload = request.body
    sig = request.META.get("HTTP_STRIPE_SIGNATURE", "")
    secret = settings.STRIPE_WEBHOOK_SECRET
    try:
        if secret:
            # Verify the signature (raises on tampering); we process the raw JSON
            # below so handlers always see a plain dict, not a StripeObject.
            stripe.Webhook.construct_event(payload, sig, secret)
        event = json.loads(payload or "{}")
    except (ValueError, stripe.error.SignatureVerificationError):
        return HttpResponse(status=400)

    try:
        webhooks.process_event(event)
    except Exception:
        # Ack anyway (Stripe retries on 5xx and we don't want a bug to wedge the
        # whole webhook), but log it so failures aren't silent.
        logging.getLogger("apps.store").exception("Stripe webhook processing failed")
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


def _entitlement_or_none(customer, offer):
    ent = Entitlement.objects.filter(customer=customer, offer=offer).first()
    return ent if ent and ent.grants_access else None


@customer_required
def product(request, offer_key):
    """The course view: modules → lessons, with drip locks and progress."""
    offer = get_object_or_404(Offer, public_key=offer_key)
    ent = _entitlement_or_none(request.customer, offer)
    if ent is None:
        messages.error(request, "You don't have access to that product.")
        return redirect("store:portal")

    since = ent.created_at
    from .models import LessonCompletion
    done_ids = set(
        LessonCompletion.objects.filter(customer=request.customer, content__offer=offer)
        .values_list("content_id", flat=True)
    )

    def lesson(l):
        return {
            "obj": l,
            "unlocked": l.is_unlocked(since),
            "unlock_date": l.unlock_date(since),
            "done": l.id in done_ids,
        }

    modules = [
        {"module": m, "lessons": [lesson(l) for l in m.lessons.all()]}
        for m in offer.modules.all()
    ]
    ungrouped = [lesson(l) for l in offer.contents.filter(module__isnull=True)]

    all_lessons = [x for m in modules for x in m["lessons"]] + ungrouped
    total = len(all_lessons)
    done = sum(1 for x in all_lessons if x["done"])
    progress = round(done / total * 100) if total else 0

    return render(request, "store/product.html", {
        "offer": offer, "entitlement": ent,
        "modules": modules, "ungrouped": ungrouped,
        "progress": progress, "done_count": done, "total_count": total,
    })


@customer_required
@require_POST
def mark_complete(request, content_id):
    """Toggle a lesson's completion for the signed-in buyer."""
    from .models import LessonCompletion
    content = get_object_or_404(ProductContent, pk=content_id)
    if _entitlement_or_none(request.customer, content.offer) is None:
        return HttpResponse("Not authorized.", status=403)
    row = LessonCompletion.objects.filter(customer=request.customer, content=content).first()
    if row:
        row.delete()
    else:
        LessonCompletion.objects.create(
            workspace=content.workspace, customer=request.customer, content=content
        )
    return redirect("store:product", offer_key=content.offer.public_key)


@customer_required
def community(request, offer_key):
    """A product's members-only discussion space (buyers + creator)."""
    from .models import Post

    offer = get_object_or_404(Offer, public_key=offer_key)
    if _entitlement_or_none(request.customer, offer) is None or not offer.community_enabled:
        messages.error(request, "That community isn't available.")
        return redirect("store:portal")

    if request.method == "POST":
        body = request.POST.get("body", "").strip()
        if body:
            Post.objects.create(
                workspace=offer.workspace, offer=offer, author=request.customer, body=body
            )
        return redirect("store:community", offer_key=offer_key)

    posts = list(offer.posts.select_related("author").prefetch_related("comments__author"))
    for p in posts:
        p.deletable = p.author_id == request.customer.id
        for c in p.comments.all():
            c.deletable = c.author_id == request.customer.id
    return render(request, "store/community.html", {
        "offer": offer, "posts": posts, "customer": request.customer,
    })


@customer_required
@require_POST
def community_comment(request, post_id):
    from .models import Comment, Post

    post = get_object_or_404(Post, pk=post_id)
    if _entitlement_or_none(request.customer, post.offer) is None:
        return HttpResponse("Not authorized.", status=403)
    body = request.POST.get("body", "").strip()
    if body:
        Comment.objects.create(
            workspace=post.workspace, post=post, author=request.customer, body=body
        )
    return redirect("store:community", offer_key=post.offer.public_key)


@customer_required
@require_POST
def community_post_delete(request, post_id):
    from .models import Post

    post = get_object_or_404(Post, pk=post_id)
    if not post.can_delete(customer=request.customer):
        return HttpResponse("Not authorized.", status=403)
    key = post.offer.public_key
    post.delete()
    return redirect("store:community", offer_key=key)


@customer_required
@require_POST
def community_comment_delete(request, comment_id):
    from .models import Comment

    c = get_object_or_404(Comment, pk=comment_id)
    if not c.can_delete(customer=request.customer):
        return HttpResponse("Not authorized.", status=403)
    key = c.post.offer.public_key
    c.delete()
    return redirect("store:community", offer_key=key)


@customer_required
def download(request, content_id):
    """Stream a lesson file — only if entitled and the lesson has dripped open."""
    content = get_object_or_404(ProductContent, pk=content_id)
    ent = _entitlement_or_none(request.customer, content.offer)
    if ent is None:
        return HttpResponse("Not authorized.", status=403)
    if not content.is_unlocked(ent.created_at):
        return HttpResponse("This lesson hasn't unlocked yet.", status=403)
    if not content.file:
        return HttpResponse("No file on this item.", status=404)
    return FileResponse(content.file.open("rb"), as_attachment=True,
                        filename=content.file.name.rsplit("/", 1)[-1])
