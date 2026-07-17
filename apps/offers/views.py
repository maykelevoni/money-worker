from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .models import Offer, ProductContent


@login_required
def offer_list(request):
    return render(request, "offers/list.html",
                  {"offers": Offer.objects.for_workspace(request.workspace)})


@login_required
@require_POST
def offer_create(request):
    name = request.POST.get("name", "").strip()
    kind = request.POST.get("kind", Offer.Kind.AFFILIATE)
    if kind not in Offer.Kind.values:
        kind = Offer.Kind.AFFILIATE
    if not name:
        messages.error(request, "Product name is required.")
        return redirect("offers:list")

    if kind == Offer.Kind.AFFILIATE:
        link = request.POST.get("affiliate_url", "").strip()
        if not link:
            messages.error(request, "An affiliate product needs an affiliate URL.")
            return redirect("offers:list")
    else:  # own product
        link = request.POST.get("checkout_url", "").strip()
        if not link:
            messages.error(request, "Your own product needs a checkout URL.")
            return redirect("offers:list")

    Offer.objects.create(
        workspace=request.workspace,
        name=name,
        kind=kind,
        vendor=request.POST.get("vendor", "").strip(),
        affiliate_url=request.POST.get("affiliate_url", "").strip(),
        commission=request.POST.get("commission", "").strip(),
        is_recurring=bool(request.POST.get("is_recurring")),
        price=request.POST.get("price", "").strip(),
        checkout_url=request.POST.get("checkout_url", "").strip(),
        landing_url=request.POST.get("landing_url", "").strip(),
    )
    messages.success(request, f"Added product “{name}”.")
    return redirect("offers:list")


@login_required
def offer_manage(request, pk):
    """Set up native selling (Stripe takes the money, we grant access) and manage
    the content buyers unlock. Turning on a paid access type makes it a sellable
    'own' product with a public /buy/ link."""
    offer = get_object_or_404(Offer, pk=pk, workspace=request.workspace)
    if request.method == "POST":
        access_type = request.POST.get("access_type", Offer.AccessType.NONE)
        if access_type not in Offer.AccessType.values:
            access_type = Offer.AccessType.NONE
        offer.access_type = access_type
        if access_type != Offer.AccessType.NONE:
            offer.kind = Offer.Kind.OWN  # only your own products sell natively

        # Price entered in dollars; stored in cents.
        raw_price = request.POST.get("price_dollars", "").strip().replace("$", "")
        if raw_price:
            try:
                offer.price_cents = int(round(float(raw_price) * 100))
            except ValueError:
                messages.error(request, "Enter the price as a number, e.g. 29 or 29.99.")
                return redirect("offers:manage", pk=offer.pk)
        offer.currency = (request.POST.get("currency", "usd").strip().lower() or "usd")[:3]
        # Amount/cadence may have changed — drop the cached Stripe price so the
        # next checkout recreates it (Stripe prices are immutable).
        offer.stripe_price_id = ""
        offer.save()
        messages.success(request, "Selling settings saved.")
        return redirect("offers:manage", pk=offer.pk)

    return render(request, "offers/manage.html", {
        "offer": offer,
        "contents": offer.contents.all(),
        "access_types": Offer.AccessType.choices,
    })


@login_required
@require_POST
def content_add(request, pk):
    offer = get_object_or_404(Offer, pk=pk, workspace=request.workspace)
    title = request.POST.get("title", "").strip()
    if not title:
        messages.error(request, "Give the content item a title.")
        return redirect("offers:manage", pk=offer.pk)
    ProductContent.objects.create(
        workspace=request.workspace,
        offer=offer,
        title=title,
        body=request.POST.get("body", "").strip(),
        file=request.FILES.get("file"),
        order=offer.contents.count(),
    )
    messages.success(request, f"Added “{title}”.")
    return redirect("offers:manage", pk=offer.pk)


@login_required
@require_POST
def content_delete(request, pk, content_id):
    offer = get_object_or_404(Offer, pk=pk, workspace=request.workspace)
    get_object_or_404(ProductContent, pk=content_id, offer=offer).delete()
    messages.success(request, "Content removed.")
    return redirect("offers:manage", pk=offer.pk)


@login_required
@require_POST
def offer_toggle(request, pk):
    offer = get_object_or_404(Offer, pk=pk, workspace=request.workspace)
    offer.is_active = not offer.is_active
    offer.save()
    messages.success(request, f"“{offer.name}” is now {'active' if offer.is_active else 'paused'}.")
    return redirect("offers:list")


@login_required
@require_POST
def offer_delete(request, pk):
    offer = get_object_or_404(Offer, pk=pk, workspace=request.workspace)
    name = offer.name
    offer.delete()
    messages.success(request, f"Deleted “{name}”.")
    return redirect("offers:list")
