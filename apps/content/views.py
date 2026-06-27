import os
import tempfile
from pathlib import Path

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.files import File
from django.db.models import Count
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.videos.services import images, uploadpost

from .models import Post

IMAGE_STYLES = ["design", "realistic", "render_3D", "anime", "general", "auto"]


def _back(pk):
    return redirect("content:post_detail", pk=pk)


def _config():
    return {"share": uploadpost.is_configured()}


@login_required
def library(request):
    """The content hub — every post (video/image/article/text) in one place."""
    posts = Post.objects.all()
    counts = {row["status"]: row["n"] for row in Post.objects.values("status").annotate(n=Count("id"))}
    return render(request, "content/library.html", {
        "posts": posts,
        "stats": {
            "total": sum(counts.values()),
            "drafts": counts.get("draft", 0),
            "scheduled": counts.get("scheduled", 0),
            "posted": counts.get("posted", 0),
        },
        "kinds": Post.Kind.choices,
        "config": _config(),
        "tab": "library",
    })


@login_required
def calendar(request):
    """Scheduled / upcoming posts — the publishing queue."""
    scheduled = Post.objects.exclude(scheduled_at=None).order_by("scheduled_at")
    return render(request, "content/calendar.html", {
        "scheduled": scheduled,
        "tab": "calendar",
    })


@login_required
def image_studio(request):
    """Generate an image from a prompt → save it into the hub as an Image post."""
    if request.method == "POST":
        prompt = request.POST.get("prompt", "").strip()
        style = request.POST.get("style", "design")
        if style not in IMAGE_STYLES:
            style = "design"
        if not prompt:
            messages.error(request, "Enter a prompt to generate an image.")
            return redirect("content:image_studio")
        tmp = Path(tempfile.gettempdir()) / f"gen_{int(timezone.now().timestamp())}.png"
        try:
            images.generate_image(prompt, tmp, style=style)
        except images.NotConfigured as e:
            messages.error(request, str(e))
            return redirect("content:image_studio")
        except Exception as e:
            messages.error(request, f"Image generation failed: {e}")
            return redirect("content:image_studio")

        post = Post(kind=Post.Kind.IMAGE, title=prompt[:120], body=prompt)
        with tmp.open("rb") as fh:
            post.media.save(f"gen_{post.title[:20]}.png", File(fh), save=False)
        post.save()
        tmp.unlink(missing_ok=True)
        messages.success(request, "Image generated 🎨 — edit the caption and publish.")
        return redirect("content:post_detail", pk=post.pk)

    return render(request, "content/image_studio.html", {
        "styles": IMAGE_STYLES,
        "config": {"images": images.is_configured()},
        "tab": "images",
    })


@login_required
def create(request):
    """Compose a new post of any kind → land on its page."""
    if request.method == "POST":
        kind = request.POST.get("kind", Post.Kind.TEXT)
        if kind not in Post.Kind.values:
            kind = Post.Kind.TEXT
        post = Post.objects.create(
            kind=kind,
            title=request.POST.get("title", "").strip(),
            body=request.POST.get("body", "").strip(),
            media=request.FILES.get("media"),
        )
        messages.success(request, "Draft created.")
        return _back(post.pk)
    return render(request, "content/compose.html", {
        "kinds": Post.Kind.choices,
        "tab": "library",
    })


@login_required
def post_detail(request, pk):
    """One post's page: edit it, choose channels, publish."""
    post = get_object_or_404(Post, pk=pk)
    if request.method == "POST":
        post.title = request.POST.get("title", post.title).strip()
        post.body = request.POST.get("body", post.body)
        sched = request.POST.get("scheduled_at", "").strip()
        post.scheduled_at = timezone.datetime.fromisoformat(sched) if sched else None
        if request.FILES.get("media"):
            post.media = request.FILES["media"]
        post.save()
        messages.success(request, "Saved.")
        return _back(pk)
    return render(request, "content/post_detail.html", {
        "p": post,
        "available_channels": [(c, uploadpost.PLATFORM_LABELS[c]) for c in post.available_channels],
        "config": _config(),
    })


@login_required
@require_POST
def publish_post(request, pk):
    """Publish the post to the selected channels via Upload-Post."""
    post = get_object_or_404(Post, pk=pk)
    channels = [c for c in request.POST.getlist("channels") if c in post.available_channels]
    if not channels:
        messages.error(request, "Pick at least one channel to publish to.")
        return _back(pk)

    title = (post.title or "").strip()
    caption = post.body
    idem = f"post-{post.pk}-{int(timezone.now().timestamp())}"
    try:
        if post.kind == Post.Kind.VIDEO:
            if not post.media:
                messages.error(request, "Attach a video file first.")
                return _back(pk)
            with post.media.open("rb") as fh:
                result = uploadpost.upload_video(
                    fh, os.path.basename(post.media.name), channels, title, caption, idempotency_key=idem
                )
        elif post.kind == Post.Kind.IMAGE:
            if not post.media:
                messages.error(request, "Attach an image first.")
                return _back(pk)
            with post.media.open("rb") as fh:
                result = uploadpost.upload_photo(
                    fh, os.path.basename(post.media.name), channels, title, caption, idempotency_key=idem
                )
        elif post.kind == Post.Kind.TEXT:
            result = uploadpost.upload_text(channels, post.body or title, idempotency_key=idem)
        else:
            messages.error(request, "Articles publish to the blog, not social channels.")
            return _back(pk)
    except uploadpost.NotConfigured as e:
        messages.error(request, str(e))
        return _back(pk)
    except Exception as e:
        messages.error(request, f"Publish failed: {e}")
        return _back(pk)

    post.channels = channels
    post.share_request_id = result.get("request_id", "")
    if result.get("results"):
        post.share_results = result["results"]
        post.status = Post.Status.POSTED
    else:
        post.status = Post.Status.PUBLISHING
    post.save()
    messages.success(request, f"Publishing to {', '.join(post.channel_labels)} 🚀")
    return _back(pk)


@login_required
@require_POST
def post_status(request, pk):
    """Poll Upload-Post for an in-flight publish."""
    post = get_object_or_404(Post, pk=pk)
    if not post.share_request_id:
        messages.error(request, "Nothing in progress for this post.")
        return _back(pk)
    try:
        data = uploadpost.check_status(post.share_request_id)
    except Exception as e:
        messages.error(request, f"Status check failed: {e}")
        return _back(pk)
    results = data.get("results") or {}
    if results:
        post.share_results = results
    if data.get("status") in ("completed", "done") or results:
        post.status = Post.Status.POSTED
        messages.success(request, "Publish complete ✅")
    else:
        messages.success(request, "Still processing — check again in a moment.")
    post.save()
    return _back(pk)


@login_required
@require_POST
def delete_post(request, pk):
    post = get_object_or_404(Post, pk=pk)
    title = str(post)
    post.delete()
    messages.success(request, f"Deleted “{title}”.")
    return redirect("content:library")
