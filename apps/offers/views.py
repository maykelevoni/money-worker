from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .models import Offer


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
