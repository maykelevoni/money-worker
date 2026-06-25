from django.contrib.auth.decorators import login_required
from django.db.models import Count
from django.shortcuts import render

from apps.leads.models import CapturePage, Lead
from apps.offers.models import Offer
from apps.sequences.models import AutomationRun, SentEmail
from apps.videos.models import Avatar, Video


def _pct(part, whole):
    return round(part / whole * 100) if whole else 0


@login_required
def index(request):
    """The command-center dashboard."""
    videos_total = Video.objects.count()
    videos_live = Video.objects.filter(status=Video.Status.POSTED).count()
    pending_approval = Video.objects.filter(
        status__in=[Video.Status.RENDERED, Video.Status.VOICED]
    ).count()

    leads_total = Lead.objects.count()
    leads_converted = Lead.objects.filter(stage=Lead.Stage.CONVERTED).count()
    leads_clicked = Lead.objects.filter(stage=Lead.Stage.CLICKED).count()

    avatars_count = Avatar.objects.count()
    products_active = Offer.objects.filter(is_active=True).count()
    pages_active = CapturePage.objects.filter(is_active=True).count()

    # The single next action — the guardrail against improvising.
    if products_active == 0:
        next_action = "Add your first product to promote (Products → add)."
    elif videos_total == 0:
        next_action = "Generate your first video in the Video Factory."
    elif pending_approval:
        next_action = f"Approve {pending_approval} video(s) waiting in the queue."
    elif pages_active == 0:
        next_action = "Create a capture page so your videos can collect leads."
    elif leads_total == 0:
        next_action = "Post a video and share its capture-page link to get your first leads."
    else:
        next_action = "Keep the funnel fed: generate + post the next video."

    context = {
        "videos_live": videos_live,
        "pending_approval": pending_approval,
        "leads_total": leads_total,
        "leads_converted": leads_converted,
        "leads_clicked": leads_clicked,
        "avatars_count": avatars_count,
        "products_active": products_active,
        "pages_active": pages_active,
        "videos_total": videos_total,
        "next_action": next_action,
        "funnel": {
            "videos": videos_total,
            "leads": leads_total,
            "clicked": leads_clicked,
            "converted": leads_converted,
        },
    }
    return render(request, "dashboard/index.html", context)


@login_required
def analytics(request):
    """Funnel performance, conversion rates, and top content."""
    videos_total = Video.objects.count()
    videos_posted = Video.objects.filter(status=Video.Status.POSTED).count()

    leads_total = Lead.objects.count()
    leads_nurturing = Lead.objects.filter(stage=Lead.Stage.NURTURING).count()
    leads_clicked = Lead.objects.filter(stage=Lead.Stage.CLICKED).count()
    leads_converted = Lead.objects.filter(stage=Lead.Stage.CONVERTED).count()

    # Funnel stages with conversion % relative to the previous stage.
    funnel = [
        {"label": "Videos posted", "icon": "🎬", "n": videos_posted, "rate": None},
        {"label": "Leads captured", "icon": "📥", "n": leads_total,
         "rate": _pct(leads_total, videos_posted) if videos_posted else None},
        {"label": "Clicked product", "icon": "🔗", "n": leads_clicked,
         "rate": _pct(leads_clicked, leads_total)},
        {"label": "Converted", "icon": "💰", "n": leads_converted,
         "rate": _pct(leads_converted, leads_total)},
    ]

    # Top videos by leads generated.
    top_videos = (
        Video.objects.annotate(n=Count("leads")).filter(n__gt=0).order_by("-n")[:5]
    )

    # Which capture pages actually convert (Lead.source_page).
    top_pages = CapturePage.objects.annotate(n=Count("leads")).order_by("-n")[:5]

    # Video pipeline breakdown.
    pipeline = (
        Video.objects.values("status").annotate(n=Count("id")).order_by("status")
    )
    status_labels = dict(Video.Status.choices)
    pipeline = [
        {"label": status_labels.get(p["status"], p["status"]), "n": p["n"]}
        for p in pipeline
    ]

    products = Offer.objects.filter(is_active=True)

    context = {
        "videos_total": videos_total,
        "videos_posted": videos_posted,
        "leads_total": leads_total,
        "leads_nurturing": leads_nurturing,
        "leads_converted": leads_converted,
        "lead_conv_rate": _pct(leads_converted, leads_total),
        "click_rate": _pct(leads_clicked, leads_total),
        "emails_sent": SentEmail.objects.count(),
        "engine_runs": AutomationRun.objects.count(),
        "products_active": products.count(),
        "products_affiliate": products.filter(kind=Offer.Kind.AFFILIATE).count(),
        "products_own": products.filter(kind=Offer.Kind.OWN).count(),
        "funnel": funnel,
        "top_videos": top_videos,
        "top_pages": top_pages,
        "pipeline": pipeline,
    }
    return render(request, "dashboard/analytics.html", context)
