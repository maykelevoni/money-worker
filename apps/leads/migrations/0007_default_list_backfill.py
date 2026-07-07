from django.db import migrations


def forwards(apps, schema_editor):
    Workspace = apps.get_model("accounts", "Workspace")
    EmailList = apps.get_model("leads", "EmailList")
    Lead = apps.get_model("leads", "Lead")
    for ws in Workspace.objects.all():
        default, _ = EmailList.objects.get_or_create(
            workspace=ws,
            name="All subscribers",
            defaults={"description": "Everyone who opted in."},
        )
        for lead in Lead.objects.filter(workspace=ws):
            lead.lists.add(default)


def backwards(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("leads", "0006_emaillist_capturepage_email_list_lead_lists"),
        ("accounts", "0002_backfill_workspaces"),
    ]

    operations = [migrations.RunPython(forwards, backwards)]
