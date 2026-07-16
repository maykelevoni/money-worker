"""First-run guided flow — escorts a brand-new workspace, page by page, from
signup to a published first post. Reuses the real screens (avatar create, the
composer, social, offers) rather than duplicating them; each step advances
`Workspace.onboarding_step` and hands off to the next.

The order (see accounts.models.ONBOARDING_STEPS):
    0  Create your influencer   -> onboarding:influencer (posts to videos:avatar_create)
    1  Make your first post     -> the real composer (content:compose)
    2  Share it                 -> onboarding:share
    3  Set up sales             -> onboarding:money  -> finish -> dashboard
"""
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from apps.content.models import Post
from apps.offers.models import Offer
from apps.social.models import SocialAccount
from apps.videos.models import Avatar

STEP_INFLUENCER, STEP_POST, STEP_SHARE, STEP_MONEY = 0, 1, 2, 3


def _home():
    return redirect("dashboard:index")


@login_required
def start(request):
    """Router — send the user to whichever step they're currently on."""
    ws = request.workspace
    if not ws or ws.onboarding_done:
        return _home()
    return redirect({
        STEP_INFLUENCER: "onboarding:influencer",
        STEP_POST: "onboarding:post",
        STEP_SHARE: "onboarding:share",
        STEP_MONEY: "onboarding:money",
    }.get(ws.onboarding_step, "onboarding:influencer"))


@login_required
def influencer(request):
    """Step 1 — welcome + create your influencer. The form posts to the existing
    videos:avatar_create, which advances the step and returns here via the router."""
    ws = request.workspace
    if not ws or ws.onboarding_done:
        return _home()
    if Avatar.objects.for_workspace(ws).exists():
        ws.advance_onboarding(STEP_POST)
        return redirect("onboarding:start")
    return render(request, "onboarding/influencer.html", {"current": STEP_INFLUENCER})


@login_required
def post(request):
    """Step 2 — reuse an in-progress draft (or make a fresh image post) and drop
    the user into the real composer, which shows the stepper while onboarding."""
    ws = request.workspace
    if not ws or ws.onboarding_done:
        return _home()
    draft = (Post.objects.for_workspace(ws)
             .filter(status=Post.Status.DRAFT).order_by("-pk").first())
    if draft is None:
        draft = Post.objects.create(
            workspace=ws, kind=Post.Kind.IMAGE, status=Post.Status.DRAFT
        )
    return redirect("content:compose", pk=draft.pk)


@login_required
def share(request):
    """Step 3 — connect a channel to publish to (or continue for now)."""
    ws = request.workspace
    if not ws or ws.onboarding_done:
        return _home()
    accounts = SocialAccount.objects.for_workspace(ws).filter(is_active=True)
    return render(request, "onboarding/share.html",
                  {"current": STEP_SHARE, "accounts": accounts})


@login_required
@require_POST
def share_continue(request):
    ws = request.workspace
    if ws and not ws.onboarding_done:
        ws.advance_onboarding(STEP_MONEY)
    return redirect("onboarding:start")


@login_required
def money(request):
    """Step 4 — the money step: line up something to sell."""
    ws = request.workspace
    if not ws or ws.onboarding_done:
        return _home()
    products = Offer.objects.for_workspace(ws).filter(is_active=True)
    return render(request, "onboarding/money.html",
                  {"current": STEP_MONEY, "products": products})


@login_required
@require_POST
def finish(request):
    ws = request.workspace
    if ws:
        ws.finish_onboarding()
    request.session["just_onboarded"] = True
    return redirect("dashboard:index")


@login_required
@require_POST
def skip(request):
    """Escape hatch — leave the flow and go straight to the app."""
    ws = request.workspace
    if ws:
        ws.finish_onboarding()
    return redirect("dashboard:index")
