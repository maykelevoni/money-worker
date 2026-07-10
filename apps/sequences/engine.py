"""The nurture engine — sends any sequence steps that are now due, per lead."""
from django.utils import timezone
from django.utils.html import escape

from apps.leads.models import Lead
from apps.leads.services import email as email_svc

from .models import AutomationRun, SentEmail, SequenceStep


def _render(body: str, lead: Lead) -> str:
    body = body.replace("{magnet}", lead.lead_magnet or "your free resource")
    # Authors can write plain text; if there are no HTML tags, turn it into safe
    # HTML (escape, blank line → paragraph, single newline → <br>) so the email
    # doesn't collapse onto one line.
    if "<" not in body:
        paragraphs = [p.strip() for p in body.split("\n\n") if p.strip()]
        body = "".join(
            "<p>" + escape(p).replace("\n", "<br>") + "</p>" for p in paragraphs
        )
    return body


def process_due_emails(
    lead: Lead | None = None, *, workspace=None, log: bool = True
) -> dict:
    """Send all due steps, scoped to a single workspace.

    - `lead` given → just that lead (workspace taken from the lead).
    - `workspace` given → every active lead in that workspace.
    - neither → loop over every workspace (safe for a future cron).

    A step is due when (now - opt-in) >= delay_days and it hasn't been sent yet.
    Safe to call repeatedly — SentEmail's unique constraint prevents double-sends.
    """
    if lead is not None:
        return _run_for_workspace(lead.workspace, [lead], log=log)

    if workspace is None:
        # No scope → run each workspace independently.
        from apps.accounts.models import Workspace

        total_sent, details = 0, []
        for ws in Workspace.objects.all():
            r = _run_for_workspace(ws, None, log=log)
            total_sent += r["sent"]
            details.append(f"{ws.slug}: {r['sent']}")
        return {"sent": total_sent, "detail": f"Sent {total_sent} email(s)."}

    return _run_for_workspace(workspace, None, log=log)


def _run_for_workspace(workspace, leads, *, log: bool) -> dict:
    """Core loop for one workspace. `leads` = explicit list, or None = all active."""
    steps = list(
        SequenceStep.objects.filter(is_active=True, workspace=workspace)
    )
    if not steps:
        return {"sent": 0, "detail": "No active sequence steps."}

    if leads is None:
        leads = Lead.objects.filter(workspace=workspace).exclude(
            stage=Lead.Stage.CONVERTED
        )

    configured = email_svc.is_configured()
    sent = 0
    skipped_no_key = 0

    for ld in leads:
        days_since = (timezone.now() - ld.created_at).days
        already = set(
            SentEmail.objects.filter(lead=ld).values_list("step_id", flat=True)
        )
        lead_list_ids = set(ld.lists.values_list("id", flat=True))
        for step in steps:
            if step.id in already or step.delay_days > days_since:
                continue
            # List-targeted step only goes to leads on that list.
            if step.email_list_id and step.email_list_id not in lead_list_ids:
                continue
            if not configured:
                skipped_no_key += 1
                continue
            try:
                email_svc.send_email(
                    to=ld.email,
                    subject=step.subject,
                    html=_render(step.body, ld),
                )
            except Exception:
                continue
            SentEmail.objects.create(lead=ld, step=step, workspace=workspace)
            sent += 1
            if ld.stage == Lead.Stage.NEW:
                ld.stage = Lead.Stage.NURTURING
                ld.save(update_fields=["stage"])

    if skipped_no_key and not configured:
        detail = f"Resend not configured — {skipped_no_key} email(s) waiting on RESEND_API_KEY."
    else:
        detail = f"Sent {sent} email(s)."

    if log:
        AutomationRun.objects.create(
            name="Email nurture engine",
            emails_sent=sent,
            detail=detail,
            workspace=workspace,
        )
    return {"sent": sent, "detail": detail}
