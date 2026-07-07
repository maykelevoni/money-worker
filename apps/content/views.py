import json
import os
import tempfile
from pathlib import Path

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.files import File
from django.db.models import Count
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.videos.services import images, openrouter, uploadpost

from .models import Post

IMAGE_STYLES = ["design", "realistic", "render_3D", "anime", "general", "auto"]


def _back(pk):
    return redirect("content:post_detail", pk=pk)


def _config():
    return {"share": uploadpost.is_configured()}


@login_required
def library(request):
    """The content hub — every post (video/image/article/text) in one place."""
    posts = Post.objects.for_workspace(request.workspace)
    counts = {row["status"]: row["n"] for row in posts.values("status").annotate(n=Count("id"))}
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
    scheduled = Post.objects.for_workspace(request.workspace).exclude(scheduled_at=None).order_by("scheduled_at")
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

        post = Post(kind=Post.Kind.IMAGE, title=prompt[:120], body=prompt,
                    workspace=request.workspace)
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


# Compose "format" (the user-facing choice) → the underlying Post.kind.
# "everything" is an image post with a caption promoted alongside it.
FORMAT_KINDS = {
    "text": Post.Kind.TEXT,
    "image": Post.Kind.IMAGE,
    "everything": Post.Kind.IMAGE,
}
KIND_FORMATS = {Post.Kind.TEXT: "text", Post.Kind.IMAGE: "image"}

# Words that mean "make me a picture" → route the AI prompt to image generation.
_IMAGE_WORDS = (
    "image", "picture", "photo", "poster", "logo", "illustration", "illustrate",
    "draw", "render", "visual", "graphic", "thumbnail", "artwork", "photograph",
)

CAPTION_SYSTEM = (
    "You are a punchy social-media copywriter. Write a single ready-to-post "
    "caption for the user's request. No preamble, no options, no quotes — return "
    "only the caption text itself, with hashtags only if they clearly help."
)


def _route_intent(prompt: str) -> str:
    """Smart routing: does this prompt want an image, or caption text?"""
    p = prompt.lower()
    return "image" if any(w in p for w in _IMAGE_WORDS) else "caption"


def _do_publish(request, post, channels):
    """Shared publish → Upload-Post. Adds a flash message; returns True on success."""
    title = (post.title or "").strip()
    caption = post.body
    idem = f"post-{post.pk}-{int(timezone.now().timestamp())}"
    try:
        if post.kind == Post.Kind.VIDEO:
            if not post.media:
                messages.error(request, "Attach a video file first.")
                return False
            with post.media.open("rb") as fh:
                result = uploadpost.upload_video(
                    fh, os.path.basename(post.media.name), channels, title, caption, idempotency_key=idem
                )
        elif post.kind == Post.Kind.IMAGE:
            if not post.media:
                messages.error(request, "Attach an image first.")
                return False
            with post.media.open("rb") as fh:
                result = uploadpost.upload_photo(
                    fh, os.path.basename(post.media.name), channels, title, caption, idempotency_key=idem
                )
        elif post.kind == Post.Kind.TEXT:
            result = uploadpost.upload_text(channels, post.body or title, idempotency_key=idem)
        else:
            messages.error(request, "Articles publish to the blog, not social channels.")
            return False
    except uploadpost.NotConfigured as e:
        messages.error(request, str(e))
        return False
    except Exception as e:
        messages.error(request, f"Publish failed: {e}")
        return False

    post.channels = channels
    post.share_request_id = result.get("request_id", "")
    if result.get("results"):
        post.share_results = result["results"]
        post.status = Post.Status.POSTED
    else:
        post.status = Post.Status.PUBLISHING
    post.save()
    messages.success(request, f"Publishing to {', '.join(post.channel_labels)} 🚀")
    return True


@login_required
def create(request):
    """New Post → open the workbench on a fresh (or reused-blank) draft."""
    post = (
        Post.objects.for_workspace(request.workspace)
        .filter(status=Post.Status.DRAFT, title="", body="", media="")
        .order_by("-created_at")
        .first()
    )
    if post is None:
        post = Post.objects.create(
            kind=Post.Kind.IMAGE, status=Post.Status.DRAFT, workspace=request.workspace
        )
    return redirect("content:compose", pk=post.pk)


@login_required
def compose(request, pk):
    """The workbench: canvas + AI prompt + sidebar widgets for one draft."""
    post = get_object_or_404(Post, pk=pk, workspace=request.workspace)
    if request.method == "POST":
        post.kind = FORMAT_KINDS.get(request.POST.get("format"), post.kind)
        allowed = uploadpost.KIND_CHANNELS.get(post.kind, [])
        post.channels = [c for c in request.POST.getlist("channels") if c in allowed]
        post.title = request.POST.get("title", "").strip()
        post.body = request.POST.get("body", "").strip()
        if request.FILES.get("media") and post.kind == Post.Kind.IMAGE:
            post.media = request.FILES["media"]
        sched = request.POST.get("scheduled_at", "").strip()
        post.scheduled_at = timezone.datetime.fromisoformat(sched) if sched else None
        post.save()

        if request.POST.get("action") == "publish":
            channels = [c for c in post.channels if c in post.available_channels]
            if not channels:
                messages.error(request, "Pick at least one platform to publish to.")
                return redirect("content:compose", pk=pk)
            if _do_publish(request, post, channels):
                return redirect("content:post_detail", pk=pk)
            return redirect("content:compose", pk=pk)

        messages.success(request, "Saved.")
        return redirect("content:compose", pk=pk)

    return render(request, "content/workbench.html", {
        "p": post,
        "format": KIND_FORMATS.get(post.kind, "image"),
        "platforms": list(uploadpost.PLATFORM_LABELS.items()),
        "kind_channels_json": json.dumps(uploadpost.KIND_CHANNELS),
        "config": {"text": openrouter.is_configured(), "images": images.is_configured()},
        "tab": "library",
    })


@login_required
@require_POST
def compose_ai(request, pk):
    """Smart AI prompt: write a caption, or generate an image — saved to the draft."""
    post = get_object_or_404(Post, pk=pk, workspace=request.workspace)
    prompt = request.POST.get("prompt", "").strip()
    if not prompt:
        return JsonResponse({"ok": False, "error": "Type what you want first."})

    if _route_intent(prompt) == "image":
        if not images.is_configured():
            return JsonResponse({"ok": False, "error": "Image AI isn't set up (FAL_API_KEY)."})
        tmp = Path(tempfile.gettempdir()) / f"gen_{int(timezone.now().timestamp())}.png"
        try:
            images.generate_image(prompt, tmp, style="design")
        except Exception as e:
            return JsonResponse({"ok": False, "error": f"Image generation failed: {e}"})
        post.kind = Post.Kind.IMAGE
        with tmp.open("rb") as fh:
            post.media.save(f"gen_{post.pk}.png", File(fh), save=False)
        post.save()
        tmp.unlink(missing_ok=True)
        return JsonResponse({"ok": True, "intent": "image", "media_url": post.media.url})

    if not openrouter.is_configured():
        return JsonResponse({"ok": False, "error": "Writing AI isn't set up (OPENROUTER_API_KEY)."})
    try:
        text = openrouter._chat(CAPTION_SYSTEM, prompt).strip()
    except Exception as e:
        return JsonResponse({"ok": False, "error": f"Writing failed: {e}"})
    post.body = text
    post.save()
    return JsonResponse({"ok": True, "intent": "caption", "body": text})


@login_required
def post_detail(request, pk):
    """One post's page: edit it, choose channels, publish."""
    post = get_object_or_404(Post, pk=pk, workspace=request.workspace)
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
    post = get_object_or_404(Post, pk=pk, workspace=request.workspace)
    channels = [c for c in request.POST.getlist("channels") if c in post.available_channels]
    if not channels:
        messages.error(request, "Pick at least one channel to publish to.")
        return _back(pk)
    _do_publish(request, post, channels)
    return _back(pk)


@login_required
@require_POST
def post_status(request, pk):
    """Poll Upload-Post for an in-flight publish."""
    post = get_object_or_404(Post, pk=pk, workspace=request.workspace)
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
    post = get_object_or_404(Post, pk=pk, workspace=request.workspace)
    title = str(post)
    post.delete()
    messages.success(request, f"Deleted “{title}”.")
    return redirect("content:library")
