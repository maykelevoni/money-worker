from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.text import slugify
from django.views.decorators.http import require_POST

from config.throttle import rate_limit

from apps.offers.models import Offer
from apps.social.models import SocialAccount
from apps.videos.models import Avatar, Video

from .models import CapturePage, EmailList, Lead, PageLink


# Build a public profile URL from a connected account's platform + handle.
# Accounts store a handle (e.g. "@duckhack"), not a full URL, so we infer it.
def _social_url(platform, handle):
    h = handle.lstrip("@").strip()
    return {
        SocialAccount.Platform.YOUTUBE: f"https://youtube.com/@{h}",
        SocialAccount.Platform.TIKTOK: f"https://tiktok.com/@{h}",
        SocialAccount.Platform.INSTAGRAM: f"https://instagram.com/{h}",
        SocialAccount.Platform.X: f"https://x.com/{h}",
        SocialAccount.Platform.PINTEREST: f"https://pinterest.com/{h}",
    }.get(platform, f"https://{h}")


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
            "lead_magnet": page.freebie.name if page.freebie else page.lead_magnet,
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


@rate_limit("capture_page", limit=20, window_seconds=60, methods=("POST",))
def page(request, slug):
    """A public capture page rendered from its CapturePage record."""
    page = get_object_or_404(CapturePage, slug=slug, is_active=True)
    if request.method == "POST":
        lead = _capture_email(request, page)
        if lead is None:
            return redirect(page.get_absolute_url())
        # A freebie has its own hosted download page — deliver it there.
        if page.freebie:
            return redirect(page.freebie.get_download_page_url())
        return render(
            request,
            "leads/thanks.html",
            {"magnet": page.lead_magnet, "success_message": page.success_message},
        )
    return render(request, page.public_template, {"page": page})


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
    pages = CapturePage.objects.for_workspace(request.workspace).select_related("offer")
    # ?layout=bio / ?layout=capture lets the "Pages" menu split into two clean
    # destinations (Bio page vs Capture page) over the same underlying model.
    layout = request.GET.get("layout")
    is_bio = layout == CapturePage.Layout.BIO
    if layout in CapturePage.Layout.values:
        pages = pages.filter(layout=layout)
    return render(
        request,
        "leads/capture_pages.html",
        {
            "pages": pages,
            "layout": layout,
            "is_bio": is_bio,
            "heading": "Bio pages" if is_bio else "Capture pages",
            "new_url": (
                "/capture-pages/new/?layout=bio" if is_bio else "/capture-pages/new/?layout=capture"
            ),
            "new_label": "+ New bio page" if is_bio else "+ New capture page",
            "subtitle": (
                "Your link-in-bio hubs — one public link that points followers "
                "everywhere you want them to go."
                if is_bio else
                "One landing page per product / lead magnet — each with its own public link."
            ),
        },
    )


def _save_page(request, page):
    page.workspace = request.workspace
    layout = request.POST.get("layout", CapturePage.Layout.CAPTURE)
    if layout not in CapturePage.Layout.values:
        layout = CapturePage.Layout.CAPTURE
    page.layout = layout
    page.headline = request.POST.get("headline", "").strip()
    # Title is an internal label — default it to the headline so it's not a
    # required field the user has to think about.
    page.title = request.POST.get("title", "").strip() or page.headline
    page.subheadline = request.POST.get("subheadline", "").strip()
    page.lead_magnet = request.POST.get("lead_magnet", "").strip()
    page.button_text = request.POST.get("button_text", "").strip() or "Send it to me →"
    page.success_message = request.POST.get("success_message", "").strip()
    page.niche = request.POST.get("niche", "").strip()
    page.is_active = bool(request.POST.get("is_active"))
    page.offer_id = request.POST.get("offer") or None
    page.freebie_id = request.POST.get("freebie") or None
    page.email_list_id = request.POST.get("email_list") or None
    page.slug = request.POST.get("slug", "").strip() or slugify(page.title)
    # Bio hubs front an influencer — their image/name is the face of the page.
    influencer_id = request.POST.get("influencer") or None
    if influencer_id and not Avatar.objects.for_workspace(
        request.workspace
    ).filter(pk=influencer_id).exists():
        influencer_id = None
    page.influencer_id = influencer_id
    if request.FILES.get("avatar"):
        page.avatar = request.FILES["avatar"]

    if not page.title or not page.headline:
        messages.error(request, "Title and headline are required.")
        return None
    # A capture page needs something to give away — a freebie product or, as a
    # fallback, a free-text lead magnet. Bio pages don't need one.
    if page.layout == CapturePage.Layout.CAPTURE and not page.freebie_id and not page.lead_magnet:
        messages.error(request, "A capture page needs a freebie (or a lead magnet).")
        return None
    try:
        page.save()
    except IntegrityError:
        messages.error(request, f"Slug “{page.slug}” is already taken — pick another.")
        return None
    _sync_bio_links(request, page)
    messages.success(request, f"Capture page “{page.title}” saved.")
    return page


def _sync_bio_links(request, page):
    """Turn the bio form's connection toggles + inline custom link into buttons.

    Idempotent by URL, so re-saving an edited page never duplicates links.
    """
    if page.layout != CapturePage.Layout.BIO:
        return
    existing = {link.url for link in page.links.all()}
    order = page.links.count()
    for acc in SocialAccount.objects.for_workspace(request.workspace):
        if not request.POST.get(f"connect_{acc.pk}"):
            continue
        url = _social_url(acc.platform, acc.handle)
        if url in existing:
            continue
        PageLink.objects.create(
            workspace=request.workspace, page=page,
            label=acc.get_platform_display(), url=url, order=order,
        )
        existing.add(url)
        order += 1
    label = request.POST.get("link_label", "").strip()
    url = request.POST.get("link_url", "").strip()
    if label and url and url not in existing:
        PageLink.objects.create(
            workspace=request.workspace, page=page,
            label=label, url=url, order=order,
        )


def _form_context(request, page, initial_layout=None):
    ws = request.workspace
    connections = SocialAccount.objects.for_workspace(ws).filter(is_active=True)
    # Pre-fill the URL each connection would add, for the live preview.
    for acc in connections:
        acc.guess_url = _social_url(acc.platform, acc.handle)
    active_offers = Offer.objects.for_workspace(ws).filter(is_active=True)
    return {
        "page": page,
        "initial_layout": initial_layout or CapturePage.Layout.CAPTURE,
        # Paid products for the "sell" picker; freebies for the lead-magnet picker.
        "offers": active_offers.exclude(kind=Offer.Kind.FREEBIE),
        "freebies": active_offers.filter(kind=Offer.Kind.FREEBIE),
        "lists": EmailList.objects.for_workspace(ws),
        "layouts": CapturePage.Layout.choices,
        "influencers": Avatar.objects.for_workspace(ws),
        "connections": connections,
    }


def _after_save_redirect(page):
    if page.layout == CapturePage.Layout.BIO:
        return redirect(f"{reverse('capture_pages')}?layout=bio")
    return redirect("capture_pages")


@login_required
def capture_page_create(request):
    if request.method == "POST":
        page = _save_page(request, CapturePage())
        if page is not None:
            return _after_save_redirect(page)
    initial_layout = request.GET.get("layout")
    if initial_layout not in CapturePage.Layout.values:
        initial_layout = CapturePage.Layout.CAPTURE
    return render(
        request,
        "leads/capture_page_form.html",
        _form_context(request, None, initial_layout=initial_layout),
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
        _form_context(request, page_obj),
    )


@login_required
@require_POST
def page_link_add(request, pk):
    page = get_object_or_404(CapturePage, pk=pk, workspace=request.workspace)
    label = request.POST.get("label", "").strip()
    url = request.POST.get("url", "").strip()
    if label and url:
        PageLink.objects.create(
            workspace=request.workspace, page=page, label=label, url=url,
            order=page.links.count(),
        )
        messages.success(request, "Link added.")
    else:
        messages.error(request, "A link needs both a label and a URL.")
    return redirect("capture_page_edit", pk=page.pk)


@login_required
@require_POST
def page_link_delete(request, pk, link_id):
    page = get_object_or_404(CapturePage, pk=pk, workspace=request.workspace)
    get_object_or_404(PageLink, pk=link_id, page=page).delete()
    messages.success(request, "Link removed.")
    return redirect("capture_page_edit", pk=page.pk)
