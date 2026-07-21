from django.contrib.auth.decorators import login_required
from django.db.models import Count
from django.shortcuts import render
from django.utils import timezone

from apps.content.models import Post
from apps.leads.models import CapturePage, Lead
from apps.offers.models import Offer
from apps.sequences.models import AutomationRun, SentEmail
from apps.videos.models import Avatar, Video


def _pct(part, whole):
    return round(part / whole * 100) if whole else 0


@login_required
def index(request):
    """The command-center dashboard."""
    ws = request.workspace
    videos = Video.objects.for_workspace(ws)
    leads = Lead.objects.for_workspace(ws)

    videos_total = videos.count()
    videos_live = videos.filter(status=Video.Status.POSTED).count()
    pending_approval = videos.filter(
        status__in=[Video.Status.RENDERED, Video.Status.VOICED]
    ).count()

    leads_total = leads.count()
    leads_converted = leads.filter(stage=Lead.Stage.CONVERTED).count()
    leads_clicked = leads.filter(stage=Lead.Stage.CLICKED).count()

    avatars_qs = Avatar.objects.for_workspace(ws)
    avatars_count = avatars_qs.count()
    # The influencer that fronts the business — the default one, else the newest.
    hero_avatar = (
        avatars_qs.filter(is_default=True).first()
        or avatars_qs.order_by("-created_at").first()
    )
    products_active = Offer.objects.for_workspace(ws).filter(is_active=True).count()
    pages_active = CapturePage.objects.for_workspace(ws).filter(is_active=True).count()
    posts_total = Post.objects.for_workspace(ws).count()
    content_total = posts_total + videos_total

    # The single next action — influencer-first, then content, then the money path.
    if avatars_count == 0:
        next_action = "Create your influencer — the face of your business."
        next_action_url, next_action_cta = "/factory/avatars/", "Create influencer"
    elif content_total == 0:
        next_action = "Make your first post with your influencer."
        next_action_url, next_action_cta = "/content/studio/", "Make a post"
    elif products_active == 0:
        next_action = "Add something to sell so your content can make money."
        next_action_url, next_action_cta = "/offers/", "Add a product"
    elif pages_active == 0:
        next_action = "Build a capture page so your content collects leads."
        next_action_url, next_action_cta = "/capture-pages/", "Build a capture page"
    elif leads_total == 0:
        next_action = "Share your content and start collecting leads."
        next_action_url, next_action_cta = "/content/", "Open your library"
    else:
        next_action = "Keep it going — make your next post."
        next_action_url, next_action_cta = "/content/studio/", "Make a post"

    # Show once, right after the guided setup finishes.
    just_onboarded = request.session.pop("just_onboarded", False)

    # A warm, time-aware greeting — the human touch at the top of the page.
    now = timezone.localtime()
    hour = now.hour
    if hour < 12:
        greeting = "Good morning"
    elif hour < 18:
        greeting = "Good afternoon"
    else:
        greeting = "Good evening"
    now_label = now.strftime("%A · %-I:%M %p")

    # One friendly sentence that reflects where things actually stand, so the
    # page feels like it's paying attention rather than reporting stats.
    if content_total == 0:
        status_line = "Your business is set up and waiting. Let's put out your first post."
    elif leads_total == 0:
        pieces = []
        if avatars_count:
            pieces.append(f"{avatars_count} influencer{'s' if avatars_count != 1 else ''}")
        if content_total:
            pieces.append(f"{content_total} post{'s' if content_total != 1 else ''} going")
        made = " and ".join(pieces) if pieces else "things moving"
        status_line = f"You've got {made}. Next up: turn that attention into leads."
    elif leads_converted:
        status_line = (
            f"{leads_converted} sale{'s' if leads_converted != 1 else ''} so far "
            f"from {leads_total} lead{'s' if leads_total != 1 else ''} — keep the momentum going."
        )
    else:
        status_line = (
            f"{leads_total} lead{'s' if leads_total != 1 else ''} in the door. "
            "Keep posting and nudge them toward the sale."
        )

    context = {
        "just_onboarded": just_onboarded,
        "greeting": greeting,
        "now_label": now_label,
        "status_line": status_line,
        "hero_avatar": hero_avatar,
        "posts_total": posts_total,
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
        "next_action_url": next_action_url,
        "next_action_cta": next_action_cta,
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
    ws = request.workspace
    videos = Video.objects.for_workspace(ws)
    leads = Lead.objects.for_workspace(ws)

    videos_total = videos.count()
    videos_posted = videos.filter(status=Video.Status.POSTED).count()

    leads_total = leads.count()
    leads_nurturing = leads.filter(stage=Lead.Stage.NURTURING).count()
    leads_clicked = leads.filter(stage=Lead.Stage.CLICKED).count()
    leads_converted = leads.filter(stage=Lead.Stage.CONVERTED).count()

    # Funnel stages with conversion % relative to the previous stage.
    funnel = [
        {"label": "Videos posted", "icon": "", "n": videos_posted, "rate": None},
        {"label": "Leads captured", "icon": "", "n": leads_total,
         "rate": _pct(leads_total, videos_posted) if videos_posted else None},
        {"label": "Clicked product", "icon": "", "n": leads_clicked,
         "rate": _pct(leads_clicked, leads_total)},
        {"label": "Converted", "icon": "", "n": leads_converted,
         "rate": _pct(leads_converted, leads_total)},
    ]

    # Bar width is proportional to the stage's own count (0 → empty bar), so an
    # empty funnel reads as empty instead of full.
    funnel_max = max((s["n"] for s in funnel), default=0)
    for s in funnel:
        s["width"] = round(s["n"] / funnel_max * 100) if funnel_max else 0

    # Top videos by leads generated.
    top_videos = (
        videos.annotate(n=Count("leads")).filter(n__gt=0).order_by("-n")[:5]
    )

    # Which capture pages actually convert (Lead.source_page).
    top_pages = (
        CapturePage.objects.for_workspace(ws).annotate(n=Count("leads")).order_by("-n")[:5]
    )

    # Video pipeline breakdown.
    pipeline = (
        videos.values("status").annotate(n=Count("id")).order_by("status")
    )
    status_labels = dict(Video.Status.choices)
    pipeline = [
        {"label": status_labels.get(p["status"], p["status"]), "n": p["n"]}
        for p in pipeline
    ]

    products = Offer.objects.for_workspace(ws).filter(is_active=True)

    context = {
        "videos_total": videos_total,
        "videos_posted": videos_posted,
        "leads_total": leads_total,
        "leads_nurturing": leads_nurturing,
        "leads_converted": leads_converted,
        "lead_conv_rate": _pct(leads_converted, leads_total),
        "click_rate": _pct(leads_clicked, leads_total),
        "emails_sent": SentEmail.objects.for_workspace(ws).count(),
        "engine_runs": AutomationRun.objects.for_workspace(ws).count(),
        "products_active": products.count(),
        "products_affiliate": products.filter(kind=Offer.Kind.AFFILIATE).count(),
        "products_own": products.filter(kind=Offer.Kind.OWN).count(),
        "funnel": funnel,
        "top_videos": top_videos,
        "top_pages": top_pages,
        "pipeline": pipeline,
    }
    return render(request, "dashboard/analytics.html", context)


@login_required
def settings(request):
    """Account hub — profile, plan, connections and workspace in one place.

    This is where 'Social accounts' now lives (as Connections) and where a
    customer manages their own account, instead of the near-empty menu it was.
    """
    from apps.accounts.models import Membership
    from apps.social.models import SocialAccount

    ws = request.workspace
    accounts = SocialAccount.objects.for_workspace(ws)
    context = {
        "ws": ws,
        "members": Membership.objects.filter(workspace=ws).select_related("user"),
        "connections": accounts,
        "connections_live": accounts.filter(is_active=True).count(),
        "avatars": Avatar.objects.for_workspace(ws),
    }
    return render(request, "dashboard/settings.html", context)
