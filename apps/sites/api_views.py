"""Public API on the control-tower host. Static sites post opt-ins here."""
import json

from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt

from .models import Website


def _cors(resp):
    resp["Access-Control-Allow-Origin"] = "*"
    resp["Access-Control-Allow-Methods"] = "POST, OPTIONS"
    resp["Access-Control-Allow-Headers"] = "Content-Type"
    return resp


@csrf_exempt
def optin_api(request):
    """Create a Lead in the site's workspace from a static site's opt-in form.

    Identified by the site's public_key (no auth cookie cross-origin).
    """
    if request.method == "OPTIONS":
        return _cors(HttpResponse(status=204))
    if request.method != "POST":
        return _cors(JsonResponse({"ok": False, "error": "POST only"}, status=405))

    if request.content_type and "application/json" in request.content_type:
        try:
            data = json.loads(request.body or "{}")
        except ValueError:
            data = {}
    else:
        data = request.POST

    key = (data.get("site_key") or "").strip()
    email = (data.get("email") or "").strip().lower()
    if not key or not email:
        return _cors(JsonResponse({"ok": False, "error": "missing fields"}, status=400))

    site = Website.objects.filter(public_key=key).first()
    if site is None:
        return _cors(JsonResponse({"ok": False, "error": "unknown site"}, status=403))

    from apps.leads.models import Lead

    lead, created = Lead.objects.get_or_create(
        workspace=site.workspace,
        email=email,
        defaults={"lead_magnet": (data.get("lead_magnet") or ""), "stage": Lead.Stage.NEW},
    )
    from apps.leads.models import EmailList

    target = None
    list_id = (data.get("list_id") or "").strip()
    if list_id:
        target = EmailList.objects.filter(pk=list_id, workspace=site.workspace).first()
    lead.lists.add(target or EmailList.default_for(site.workspace))
    if created:
        try:
            from apps.sequences.engine import process_due_emails

            process_due_emails(lead, log=False)
        except Exception:
            pass
    return _cors(JsonResponse({"ok": True}))
