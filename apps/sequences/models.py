from django.db import models

from apps.accounts.models import WorkspaceOwned


class SequenceStep(WorkspaceOwned):
    """One email in the nurture drip. Steps fire in `delay_days` order after opt-in."""

    order = models.PositiveIntegerField(default=0)
    delay_days = models.PositiveIntegerField(
        default=0, help_text="Days after opt-in to send (0 = immediately)"
    )
    subject = models.CharField(max_length=255)
    body = models.TextField(help_text="HTML allowed. Use {magnet} as a placeholder.")
    email_list = models.ForeignKey(
        "leads.EmailList",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="steps",
        help_text="Only send to this list (blank = everyone in the workspace)",
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["delay_days", "order"]

    def __str__(self):
        return f"Day {self.delay_days}: {self.subject}"


class SentEmail(WorkspaceOwned):
    """Record of a step delivered to a lead (prevents double-sends)."""

    lead = models.ForeignKey(
        "leads.Lead", on_delete=models.CASCADE, related_name="sent_emails"
    )
    step = models.ForeignKey(
        SequenceStep, on_delete=models.CASCADE, related_name="sends"
    )
    sent_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("lead", "step")


class AutomationRun(WorkspaceOwned):
    """Log of each engine run, for the Automations page."""

    name = models.CharField(max_length=100)
    emails_sent = models.PositiveIntegerField(default=0)
    detail = models.CharField(max_length=300, blank=True)
    ran_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-ran_at"]

    def __str__(self):
        return f"{self.name} @ {self.ran_at:%Y-%m-%d %H:%M}"
