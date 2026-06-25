from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.leads.models import Lead
from apps.leads.services import email as email_svc

from .engine import process_due_emails
from .models import AutomationRun, SequenceStep


@login_required
def step_list(request):
    return render(
        request,
        "sequences/list.html",
        {
            "steps": SequenceStep.objects.all(),
            "email_configured": email_svc.is_configured(),
        },
    )


@login_required
@require_POST
def step_create(request):
    subject = request.POST.get("subject", "").strip()
    body = request.POST.get("body", "").strip()
    if not subject or not body:
        messages.error(request, "Subject and body are required.")
        return redirect("sequences:list")
    SequenceStep.objects.create(
        delay_days=int(request.POST.get("delay_days") or 0),
        subject=subject,
        body=body,
    )
    messages.success(request, "Email step added.")
    return redirect("sequences:list")


@login_required
@require_POST
def step_delete(request, pk):
    get_object_or_404(SequenceStep, pk=pk).delete()
    messages.success(request, "Step deleted.")
    return redirect("sequences:list")


@login_required
@require_POST
def step_toggle(request, pk):
    step = get_object_or_404(SequenceStep, pk=pk)
    step.is_active = not step.is_active
    step.save()
    messages.success(request, f"Step {'activated' if step.is_active else 'paused'}.")
    return redirect("sequences:list")


@login_required
@require_POST
def load_starter(request):
    """One-click starter 3-email drip."""
    if SequenceStep.objects.exists():
        messages.error(request, "You already have steps — clear them first.")
        return redirect("sequences:list")
    starter = [
        (0, "Your free AI tools cheat sheet 🎁",
         "<p>Hey!</p><p>Here's <strong>{magnet}</strong> as promised: <a href='#'>download</a>.</p>"
         "<p>I'll send you the best AI tools for creators over the next few days.</p>"),
        (2, "The one AI tool I'd start with",
         "<p>If you only try one tool this week, make it this one…</p>"
         "<p>It saves creators hours every day. <a href='#'>See it here</a>.</p>"),
        (4, "Ready to level up your content?",
         "<p>Here's the tool I personally recommend for serious creators.</p>"
         "<p><a href='#'>Grab it here</a> — you won't regret it.</p>"),
    ]
    for i, (d, s, b) in enumerate(starter):
        SequenceStep.objects.create(order=i, delay_days=d, subject=s, body=b)
    messages.success(request, "Loaded a 3-email starter sequence. Edit the links!")
    return redirect("sequences:list")


@login_required
def automations(request):
    runs = AutomationRun.objects.all()[:15]
    return render(
        request,
        "sequences/automations.html",
        {
            "runs": runs,
            "last_run": runs[0] if runs else None,
            "leads_total": Lead.objects.count(),
            "active_steps": SequenceStep.objects.filter(is_active=True).count(),
            "email_configured": email_svc.is_configured(),
        },
    )


@login_required
@require_POST
def run_now(request):
    result = process_due_emails()
    messages.success(request, f"Engine ran — {result['detail']}")
    return redirect("sequences:automations")


@login_required
def scheduler(request):
    return render(
        request,
        "sequences/scheduler.html",
        {"steps": SequenceStep.objects.filter(is_active=True)},
    )
