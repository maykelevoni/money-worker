from django.shortcuts import redirect

from .models import Membership


class OnboardingMiddleware:
    """Escorts a not-yet-onboarded workspace through the first-run flow. If the
    user tries to wander off (dashboard, research, websites…) before finishing,
    they're pulled back to their current step. Must sit after WorkspaceMiddleware.

    Prefixes the flow needs to function stay allowed so the steps actually work
    (the avatar screen, the composer + its AJAX endpoints, social, offers)."""

    # Always allowed (auth, static, public API, admin, the flow router itself).
    ALWAYS = ("/start", "/static", "/media", "/admin",
              "/accounts/logout", "/accounts/login", "/accounts/password",
              "/settings", "/api/")
    # Screens the guided steps hand off to — allowed so the steps can run.
    FLOW = ("/factory/avatars", "/content", "/social", "/offers", "/capture-pages")

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        ws = getattr(request, "workspace", None)
        user = getattr(request, "user", None)
        if (user is not None and user.is_authenticated and ws is not None
                and not ws.onboarding_done):
            path = request.path
            allowed = any(path.startswith(p) for p in self.ALWAYS + self.FLOW)
            if not allowed:
                return redirect("onboarding:start")
        return self.get_response(request)


class WorkspaceMiddleware:
    """Resolves the active Workspace for the logged-in user and puts it on the
    request as `request.workspace`. Must sit after AuthenticationMiddleware.

    Active workspace = the one pinned in the session, else the user's default
    membership, else their first. Anonymous requests get `request.workspace = None`.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.workspace = None
        user = getattr(request, "user", None)
        if user is not None and user.is_authenticated:
            request.workspace = self._resolve(request, user)
        return self.get_response(request)

    def _resolve(self, request, user):
        memberships = Membership.objects.filter(user=user).select_related("workspace")
        pinned = request.session.get("workspace_id")
        if pinned:
            m = memberships.filter(workspace_id=pinned).first()
            if m:
                return m.workspace
        m = memberships.filter(is_default=True).first() or memberships.first()
        if m:
            request.session["workspace_id"] = m.workspace_id
            return m.workspace
        return None
