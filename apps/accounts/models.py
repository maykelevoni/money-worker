from django.conf import settings
from django.db import models

# First-run flow: the ordered steps a new workspace is escorted through.
# `Workspace.onboarding_step` holds the next step index; >= ONBOARDING_STEPS = done.
ONBOARDING_STEPS = 4


class Workspace(models.Model):
    """A tenant — one customer's private space. Every owned row points at one.

    Built now with a single Workspace (Mayke's), but the ownership stamp exists
    from the first model so the app can become multi-tenant without a rewrite.
    """

    name = models.CharField(max_length=200)
    slug = models.SlugField(unique=True, help_text="Internal id, e.g. 'mayke'")
    created_at = models.DateTimeField(auto_now_add=True)
    # First-run guided flow: index of the next step to complete. Starts at 0
    # (create your influencer); reaching ONBOARDING_STEPS means fully set up.
    onboarding_step = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    @property
    def onboarding_done(self):
        return self.onboarding_step >= ONBOARDING_STEPS

    def advance_onboarding(self, to_step):
        """Move the flow forward to `to_step` (never backward). Saves if changed."""
        if not self.onboarding_done and to_step > self.onboarding_step:
            self.onboarding_step = to_step
            self.save(update_fields=["onboarding_step"])

    def finish_onboarding(self):
        if not self.onboarding_done:
            self.onboarding_step = ONBOARDING_STEPS
            self.save(update_fields=["onboarding_step"])


class Membership(models.Model):
    """Links a User to a Workspace. A user can belong to several workspaces."""

    class Role(models.TextChoices):
        OWNER = "owner", "Owner"
        MEMBER = "member", "Member"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="memberships"
    )
    workspace = models.ForeignKey(
        Workspace, on_delete=models.CASCADE, related_name="memberships"
    )
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.OWNER)
    is_default = models.BooleanField(
        default=False, help_text="Which workspace opens on login"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "workspace")

    def __str__(self):
        return f"{self.user} → {self.workspace} ({self.role})"


class TenantQuerySet(models.QuerySet):
    def for_workspace(self, workspace):
        return self.filter(workspace=workspace)


TenantManager = models.Manager.from_queryset(TenantQuerySet)


class WorkspaceOwned(models.Model):
    """Abstract base: stamps a row with its owning Workspace and exposes
    `.objects.for_workspace(ws)` for explicit, leak-proof scoping in views.

    NOTE: `workspace` starts nullable so the FK can be added to tables that
    already hold rows; a data migration backfills every row, then a follow-up
    migration flips it to non-null. See docs/phase-0-tenancy.md.
    """

    workspace = models.ForeignKey(
        "accounts.Workspace",
        on_delete=models.CASCADE,
        related_name="+",
    )

    objects = TenantManager()

    class Meta:
        abstract = True
