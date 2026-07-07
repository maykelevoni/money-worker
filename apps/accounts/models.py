from django.conf import settings
from django.db import models


class Workspace(models.Model):
    """A tenant — one customer's private space. Every owned row points at one.

    Built now with a single Workspace (Mayke's), but the ownership stamp exists
    from the first model so the app can become multi-tenant without a rewrite.
    """

    name = models.CharField(max_length=200)
    slug = models.SlugField(unique=True, help_text="Internal id, e.g. 'mayke'")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


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
