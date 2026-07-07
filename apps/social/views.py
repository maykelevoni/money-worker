from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .models import SocialAccount


@login_required
def account_list(request):
    accounts = SocialAccount.objects.for_workspace(request.workspace)
    return render(request, "social/list.html", {
        "accounts": accounts,
        "platforms": SocialAccount.Platform.choices,
    })


@login_required
@require_POST
def account_create(request):
    platform = request.POST.get("platform")
    handle = request.POST.get("handle", "").strip()
    up_profile = request.POST.get("up_profile", "").strip()
    if platform not in SocialAccount.Platform.values or not handle or not up_profile:
        messages.error(request, "Platform, handle and Upload-Post profile are all required.")
        return redirect("social:list")
    SocialAccount.objects.create(
        workspace=request.workspace,
        platform=platform,
        handle=handle,
        display_name=request.POST.get("display_name", "").strip(),
        up_profile=up_profile,
        status=SocialAccount.Status.CONNECTED
        if request.POST.get("connected")
        else SocialAccount.Status.DISCONNECTED,
    )
    messages.success(request, f"Added {handle}.")
    return redirect("social:list")


@login_required
@require_POST
def account_toggle(request, pk):
    acc = get_object_or_404(SocialAccount, pk=pk, workspace=request.workspace)
    acc.is_active = not acc.is_active
    acc.save(update_fields=["is_active"])
    messages.success(request, f"{acc.handle} is now {'active' if acc.is_active else 'paused'}.")
    return redirect("social:list")


@login_required
@require_POST
def account_delete(request, pk):
    acc = get_object_or_404(SocialAccount, pk=pk, workspace=request.workspace)
    handle = acc.handle
    acc.delete()
    messages.success(request, f"Removed {handle}.")
    return redirect("social:list")
