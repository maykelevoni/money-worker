"""The nurture engine — sends any sequence steps that are now due, per lead."""
from django.utils import timezone

from apps.leads.models import Lead
from apps.leads.services import email as email_svc

from .models import AutomationRun, SentEmail, SequenceStep


def _render(body: str, lead: Lead) -> str:
    return body.replace("{magnet}", lead.lead_magnet or "your free resource")


def process_due_emails(lead: Lead | None = None, *, log: bool = True) -> dict:
    """Send all due steps. If `lead` given, only that lead; else every active lead.

    A step is due when (now - opt-in) >= delay_days and it hasn't been sent yet.
    Safe to call repeatedly — SentEmail's unique constraint prevents double-sends.
    """
    steps = list(SequenceStep.objects.filter(is_active=True))
    if not steps:
        return {"sent": 0, "detail": "No active sequence steps."}

    if lead is not None:
        leads = [lead]
    else:
        leads = Lead.objects.exclude(stage=Lead.Stage.CONVERTED)

    configured = email_svc.is_configured()
    sent = 0
    skipped_no_key = 0

    for ld in leads:
        days_since = (timezone.now() - ld.created_at).days
        already = set(
            SentEmail.objects.filter(lead=ld).values_list("step_id", flat=True)
        )
        for step in steps:
            if step.id in already or step.delay_days > days_since:
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
            SentEmail.objects.create(lead=ld, step=step)
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
            name="Email nurture engine", emails_sent=sent, detail=detail
        )
    return {"sent": sent, "detail": detail}
