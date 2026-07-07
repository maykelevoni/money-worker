from django.db import migrations
from django.utils.text import slugify

# Every owned model — each existing row is assigned to the primary workspace.
OWNED = [
    ("content", "Post"),
    ("leads", "CapturePage"),
    ("leads", "Lead"),
    ("offers", "Offer"),
    ("sequences", "SequenceStep"),
    ("sequences", "SentEmail"),
    ("sequences", "AutomationRun"),
    ("videos", "Avatar"),
    ("videos", "TopicIdea"),
    ("videos", "Video"),
]


def forwards(apps, schema_editor):
    Workspace = apps.get_model("accounts", "Workspace")
    Membership = apps.get_model("accounts", "Membership")
    User = apps.get_model("auth", "User")

    # Primary workspace owns all pre-existing data (it's all Mayke's).
    primary, _ = Workspace.objects.get_or_create(
        slug="mayke", defaults={"name": "Mayke's Workspace"}
    )

    users = list(User.objects.all())
    mayke = next((u for u in users if u.username == "mayke"), None)
    owner = (
        mayke
        or next((u for u in users if u.is_superuser), None)
        or (users[0] if users else None)
    )
    if owner:
        Membership.objects.get_or_create(
            user=owner,
            workspace=primary,
            defaults={"role": "owner", "is_default": True},
        )

    # Every other user gets their own workspace; the 'claude' preview user's is
    # a throwaway used to prove tenant isolation.
    for u in users:
        if owner and u.pk == owner.pk:
            continue
        if u.username == "claude":
            ws, _ = Workspace.objects.get_or_create(
                slug="claude-preview", defaults={"name": "Claude Preview"}
            )
        else:
            ws, _ = Workspace.objects.get_or_create(
                slug=slugify(u.username) or f"user-{u.pk}",
                defaults={"name": f"{u.username}'s Workspace"},
            )
        Membership.objects.get_or_create(
            user=u, workspace=ws, defaults={"role": "owner", "is_default": True}
        )

    # Stamp all existing rows with the primary workspace.
    for app_label, model_name in OWNED:
        Model = apps.get_model(app_label, model_name)
        Model.objects.filter(workspace__isnull=True).update(workspace=primary)


def backwards(apps, schema_editor):
    # Non-destructive rollback: unstamp rows so the field-add can reverse.
    for app_label, model_name in OWNED:
        Model = apps.get_model(app_label, model_name)
        Model.objects.update(workspace=None)


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0001_initial"),
        ("content", "0002_post_workspace"),
        ("offers", "0003_offer_workspace"),
        ("sequences", "0002_automationrun_workspace_sentemail_workspace_and_more"),
        ("videos", "0006_avatar_workspace_topicidea_workspace_video_workspace"),
        ("leads", "0004_capturepage_workspace_lead_workspace_and_more"),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
