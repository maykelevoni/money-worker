from .models import Membership


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
