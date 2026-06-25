from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from apps.videos.models import Video

from .models import Lead

# The freebie offered on the capture page. Edit freely.
LEAD_MAGNET = "The 25 AI Tools Content Creators Are Using in 2026 (free cheat sheet)"


@login_required
def lead_list(request):
    leads = Lead.objects.select_related("source_video").all()
    counts = {s.value: leads.filter(stage=s.value).count() for s in Lead.Stage}
    return render(
        request,
        "leads/list.html",
        {"leads": leads, "counts": counts, "total": leads.count()},
    )


def capture(request):
    """Public lead-capture / bio-link landing page."""
    if request.method == "POST":
        email_addr = request.POST.get("email", "").strip().lower()
        if not email_addr:
            messages.error(request, "Please enter your email.")
            return redirect(request.path)

        source_video = None
        vid = request.GET.get("v") or request.POST.get("v")
        if vid:
            source_video = Video.objects.filter(pk=vid).first()

        lead, created = Lead.objects.get_or_create(
            email=email_addr,
            defaults={
                "lead_magnet": LEAD_MAGNET,
                "source_video": source_video,
                "stage": Lead.Stage.NEW,
            },
        )

        # Enroll in the nurture sequence — fires any day-0 email immediately.
        if created:
            try:
                from apps.sequences.engine import process_due_emails

                process_due_emails(lead, log=False)
            except Exception:
                pass

        return render(request, "leads/thanks.html", {"magnet": LEAD_MAGNET})

    return render(request, "leads/capture.html", {"magnet": LEAD_MAGNET})
