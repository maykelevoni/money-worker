from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.text import slugify
from django.views.decorators.http import require_POST

from apps.offers.models import Offer
from apps.videos.models import Video

from .models import CapturePage, EmailList, Lead


# ---------------------------------------------------------------------------
# Public
# ---------------------------------------------------------------------------
def _capture_email(request, page):
    """Shared opt-in handling: create the Lead + fire the day-0 welcome email."""
    email_addr = request.POST.get("email", "").strip().lower()
    if not email_addr:
        messages.error(request, "Please enter your email.")
        return None

    source_video = None
    vid = request.GET.get("v") or request.POST.get("v")
    if vid:
        source_video = Video.objects.filter(pk=vid, workspace=page.workspace).first()

    lead, created = Lead.objects.get_or_create(
        workspace=page.workspace,
        email=email_addr,
        defaults={
            "lead_magnet": page.lead_magnet,
            "source_video": source_video,
            "source_page": page,
            "stage": Lead.Stage.NEW,
        },
    )
    # Join the page's list (or the workspace default).
    lead.lists.add(page.email_list or EmailList.default_for(page.workspace))

    # Enroll in the nurture sequence — fires any day-0 email immediately.
    if created:
        try:
            from apps.sequences.engine import process_due_emails

            process_due_emails(lead, log=False)
        except Exception:
            pass
    return lead


def page(request, slug):
    """A public capture page rendered from its CapturePage record."""
    page = get_object_or_404(CapturePage, slug=slug, is_active=True)
    if request.method == "POST":
        lead = _capture_email(request, page)
        if lead is None:
            return redirect(page.get_absolute_url())
        return render(
            request,
            "leads/thanks.html",
            {"magnet": page.lead_magnet, "success_message": page.success_message},
        )
    return render(request, "leads/page.html", {"page": page})


def capture(request):
    """Legacy /free/ — resolves to the first active capture page (keeps old links alive)."""
    first = CapturePage.objects.filter(is_active=True).first()
    if not first:
        return render(request, "leads/no_page.html")
    url = first.get_absolute_url()
    qs = request.GET.urlencode()
    return redirect(f"{url}?{qs}" if qs else url)


# ---------------------------------------------------------------------------
# Internal (login required)
# ---------------------------------------------------------------------------
@login_required
def lead_list(request):
    from django.db.models import Count

    ws = request.workspace
    lists = list(EmailList.objects.for_workspace(ws).annotate(n=Count("leads")))
    leads = (
        Lead.objects.for_workspace(ws)
        .select_related("source_video", "source_page")
        .prefetch_related("lists")
    )
    selected = request.GET.get("list") or ""
    if selected:
        leads = leads.filter(lists__id=selected)
    counts = {s.value: leads.filter(stage=s.value).count() for s in Lead.Stage}
    return render(
        request,
        "leads/list.html",
        {
            "leads": leads,
            "counts": counts,
            "total": leads.count(),
            "lists": lists,
            "selected_list": selected,
        },
    )


@login_required
@require_POST
def list_create(request):
    name = request.POST.get("name", "").strip()
    if name:
        EmailList.objects.get_or_create(workspace=request.workspace, name=name)
        messages.success(request, f"List “{name}” created.")
    return redirect("leads")


@login_required
@require_POST
def list_delete(request, pk):
    get_object_or_404(EmailList, pk=pk, workspace=request.workspace).delete()
    messages.success(request, "List deleted.")
    return redirect("leads")


@login_required
@require_POST
def lead_add_list(request, pk):
    lead = get_object_or_404(Lead, pk=pk, workspace=request.workspace)
    lst = get_object_or_404(
        EmailList, pk=request.POST.get("list"), workspace=request.workspace
    )
    lead.lists.add(lst)
    return redirect(request.META.get("HTTP_REFERER") or "leads")


@login_required
@require_POST
def lead_remove_list(request, pk, list_id):
    lead = get_object_or_404(Lead, pk=pk, workspace=request.workspace)
    lead.lists.remove(list_id)
    return redirect(request.META.get("HTTP_REFERER") or "leads")


@login_required
def capture_pages(request):
    return render(
        request,
        "leads/capture_pages.html",
        {"pages": CapturePage.objects.for_workspace(request.workspace).select_related("offer")},
    )


def _save_page(request, page):
    page.workspace = request.workspace
    page.title = request.POST.get("title", "").strip()
    page.headline = request.POST.get("headline", "").strip()
    page.subheadline = request.POST.get("subheadline", "").strip()
    page.lead_magnet = request.POST.get("lead_magnet", "").strip()
    page.button_text = request.POST.get("button_text", "").strip() or "Send it to me →"
    page.success_message = request.POST.get("success_message", "").strip()
    page.niche = request.POST.get("niche", "").strip()
    page.is_active = bool(request.POST.get("is_active"))
    page.offer_id = request.POST.get("offer") or None
    page.email_list_id = request.POST.get("email_list") or None
    page.slug = request.POST.get("slug", "").strip() or slugify(page.title)

    if not page.title or not page.headline or not page.lead_magnet:
        messages.error(request, "Title, headline and lead magnet are required.")
        return None
    try:
        page.save()
    except IntegrityError:
        messages.error(request, f"Slug “{page.slug}” is already taken — pick another.")
        return None
    messages.success(request, f"Capture page “{page.title}” saved.")
    return page


@login_required
def capture_page_create(request):
    if request.method == "POST":
        if _save_page(request, CapturePage()) is not None:
            return redirect("capture_pages")
    return render(
        request,
        "leads/capture_page_form.html",
        {"page": None, "offers": Offer.objects.for_workspace(request.workspace).filter(is_active=True),
         "lists": EmailList.objects.for_workspace(request.workspace)},
    )


@login_required
def capture_page_edit(request, pk):
    page_obj = get_object_or_404(CapturePage, pk=pk, workspace=request.workspace)
    if request.method == "POST":
        if _save_page(request, page_obj) is not None:
            return redirect("capture_pages")
    return render(
        request,
        "leads/capture_page_form.html",
        {"page": page_obj, "offers": Offer.objects.for_workspace(request.workspace).filter(is_active=True),
         "lists": EmailList.objects.for_workspace(request.workspace)},
    )
