from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .models import Offer


@login_required
def offer_list(request):
    return render(request, "offers/list.html", {"offers": Offer.objects.all()})


@login_required
@require_POST
def offer_create(request):
    name = request.POST.get("name", "").strip()
    url = request.POST.get("affiliate_url", "").strip()
    if not name or not url:
        messages.error(request, "Name and affiliate URL are required.")
        return redirect("offers:list")
    Offer.objects.create(
        name=name,
        vendor=request.POST.get("vendor", "").strip(),
        affiliate_url=url,
        landing_url=request.POST.get("landing_url", "").strip(),
        commission=request.POST.get("commission", "").strip(),
        is_recurring=bool(request.POST.get("is_recurring")),
    )
    messages.success(request, f"Added offer “{name}”.")
    return redirect("offers:list")


@login_required
@require_POST
def offer_toggle(request, pk):
    offer = get_object_or_404(Offer, pk=pk)
    offer.is_active = not offer.is_active
    offer.save()
    messages.success(request, f"“{offer.name}” is now {'active' if offer.is_active else 'paused'}.")
    return redirect("offers:list")


@login_required
@require_POST
def offer_delete(request, pk):
    offer = get_object_or_404(Offer, pk=pk)
    name = offer.name
    offer.delete()
    messages.success(request, f"Deleted “{name}”.")
    return redirect("offers:list")
