import calendar as _cal
import json
import os
import tempfile
from datetime import date, timedelta
from pathlib import Path

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.files import File
from django.db.models import Count, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.social import publish as social_publish
from apps.social.models import SocialAccount
from apps.videos.models import Avatar
from apps.videos.services import images, openrouter, uploadpost

from .models import Post, PostImage

IMAGE_STYLES = ["design", "realistic", "render_3D", "anime", "general", "auto"]


def _select_image(post, pi):
    """Mark one gallery image as the post's chosen image and mirror it into
    Post.media (same stored object, no re-upload) so publishing is unchanged."""
    post.images.exclude(pk=pi.pk).update(is_selected=False)
    if not pi.is_selected:
        pi.is_selected = True
        pi.save(update_fields=["is_selected"])
    # An article/video keeps its kind when it gains a hero image; only the
    # auto-derived text↔image kinds flip to IMAGE on selection.
    if post.kind not in (Post.Kind.ARTICLE, Post.Kind.VIDEO):
        post.kind = Post.Kind.IMAGE
    post.media.name = pi.image.name
    post.save(update_fields=["media", "kind"])


def _back(pk):
    return redirect("content:post_detail", pk=pk)


def _config():
    return {"share": uploadpost.is_configured()}


@login_required
def library(request):
    """The content hub — every post (video/image/article/text) in one place."""
    all_posts = Post.objects.for_workspace(request.workspace)
    counts = {row["status"]: row["n"] for row in all_posts.values("status").annotate(n=Count("id"))}

    q = request.GET.get("q", "").strip()
    kind = request.GET.get("kind", "")
    status = request.GET.get("status", "")
    posts = all_posts
    if q:
        posts = posts.filter(Q(title__icontains=q) | Q(body__icontains=q))
    if kind:
        posts = posts.filter(kind=kind)
    if status:
        posts = posts.filter(status=status)

    return render(request, "content/library.html", {
        "posts": posts,
        "stats": {
            "total": sum(counts.values()),
            "drafts": counts.get("draft", 0),
            "scheduled": counts.get("scheduled", 0),
            "posted": counts.get("posted", 0),
        },
        "kinds": Post.Kind.choices,
        "statuses": Post.Status.choices,
        "filters": {"q": q, "kind": kind, "status": status},
        "is_filtered": bool(q or kind or status),
        "config": _config(),
        "tab": "library",
    })


@login_required
def calendar(request):
    """A month calendar of scheduled posts, plus an upcoming list."""
    ws = request.workspace
    today = timezone.localdate()

    try:
        year, month = (int(x) for x in request.GET.get("month", "").split("-"))
        base = date(year, month, 1)
    except (ValueError, TypeError):
        base = today.replace(day=1)

    scheduled = list(
        Post.objects.for_workspace(ws).exclude(scheduled_at=None).order_by("scheduled_at")
    )
    by_day = {}
    for p in scheduled:
        d = timezone.localtime(p.scheduled_at).date()
        by_day.setdefault(d, []).append(p)

    weeks = []
    for week in _cal.Calendar(firstweekday=6).monthdatescalendar(base.year, base.month):
        weeks.append([
            {"date": d, "day": d.day, "in_month": d.month == base.month,
             "today": d == today, "posts": by_day.get(d, [])}
            for d in week
        ])

    prev_month = (base - timedelta(days=1)).replace(day=1)
    next_month = (base + timedelta(days=32)).replace(day=1)
    upcoming = [p for p in scheduled if timezone.localtime(p.scheduled_at).date() >= today][:6]

    return render(request, "content/calendar.html", {
        "weeks": weeks,
        "month_label": base.strftime("%B %Y"),
        "prev_month": prev_month.strftime("%Y-%m"),
        "next_month": next_month.strftime("%Y-%m"),
        "is_current": base == today.replace(day=1),
        "weekday_names": ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"],
        "upcoming": upcoming,
        "has_scheduled": bool(scheduled),
        "tab": "calendar",
    })


@login_required
def image_studio(request):
    """Folded into the New Post workbench — kept only to redirect old links."""
    return redirect("content:create")


CAPTION_SYSTEM = (
    "You are a punchy social-media copywriter. Write a single ready-to-post "
    "caption for the user's request. No preamble, no options, no quotes — return "
    "only the caption text itself, with hashtags only if they clearly help."
)


def _do_publish(request, post, accounts):
    """Publish a post to the chosen SocialAccounts, grouped by Upload-Post
    profile. Adds a flash message; returns True on success."""
    if post.kind == Post.Kind.ARTICLE:
        messages.error(request, "Articles publish to the blog, not social channels.")
        return False
    if post.kind in (Post.Kind.VIDEO, Post.Kind.IMAGE) and not post.media:
        messages.error(request, "Attach a file first.")
        return False

    title = (post.title or "").strip()
    caption = post.body
    ts = int(timezone.now().timestamp())
    results, last_id, errors, done_platforms = {}, "", [], set()

    for profile, platforms in social_publish.group_by_profile(accounts).items():
        idem = f"post-{post.pk}-{profile}-{ts}"
        try:
            if post.kind == Post.Kind.VIDEO:
                with post.media.open("rb") as fh:
                    r = uploadpost.upload_video(
                        fh, os.path.basename(post.media.name), platforms, title, caption,
                        user=profile, idempotency_key=idem,
                    )
            elif post.kind == Post.Kind.IMAGE:
                with post.media.open("rb") as fh:
                    r = uploadpost.upload_photo(
                        fh, os.path.basename(post.media.name), platforms, title, caption,
                        user=profile, idempotency_key=idem,
                    )
            else:  # TEXT
                r = uploadpost.upload_text(
                    platforms, post.body or title, user=profile, idempotency_key=idem
                )
        except uploadpost.NotConfigured as e:
            messages.error(request, str(e))
            return False
        except Exception as e:
            errors.append(f"{profile}: {e}")
            continue
        last_id = r.get("request_id", "") or last_id
        if r.get("results"):
            results.update(r["results"])
        done_platforms.update(platforms)

    post.channels = list(done_platforms)
    post.share_request_id = last_id
    if results:
        post.share_results = results
        post.status = Post.Status.POSTED
    elif last_id:
        post.status = Post.Status.PUBLISHING
    post.save()

    if errors:
        messages.warning(request, "Some posts failed — " + "; ".join(errors))
    if results or last_id:
        messages.success(request, f"Publishing to {', '.join(a.handle for a in accounts)} ")
    return bool(results or last_id)


@login_required
def studio(request):
    """One entry for everything you can make — pick a kind, it routes to the builder."""
    return render(request, "content/studio.html", {})


@login_required
def create(request):
    """New Post → open the workbench on a fresh (or reused-blank) draft.

    Honours ?kind=text|image|article so the launcher can start the right kind
    (an article stays an article; see compose()'s kind rules)."""
    kinds = {"text": Post.Kind.TEXT, "image": Post.Kind.IMAGE, "article": Post.Kind.ARTICLE}
    chosen = kinds.get(request.GET.get("kind", ""))
    if chosen:
        post = Post.objects.create(
            kind=chosen, status=Post.Status.DRAFT, workspace=request.workspace
        )
        return redirect("content:compose", pk=post.pk)

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
    """The studio: image gallery + content editor + AI prompt bar for one draft."""
    post = get_object_or_404(Post, pk=pk, workspace=request.workspace)
    if request.method == "POST":
        # Kind is derived for text↔image posts (selected image → image, else
        # text), but an article/video keeps the kind it was created with.
        if post.kind not in (Post.Kind.ARTICLE, Post.Kind.VIDEO):
            post.kind = Post.Kind.IMAGE if post.images.filter(is_selected=True).exists() else Post.Kind.TEXT
        post.title = request.POST.get("title", "").strip()
        post.body = request.POST.get("body", "").strip()
        sched = request.POST.get("scheduled_at", "").strip()
        post.scheduled_at = timezone.datetime.fromisoformat(sched) if sched else None
        post.save()

        if request.POST.get("action") == "publish":
            accounts = social_publish.accounts_for(
                request.workspace, post.available_channels, request.POST.getlist("accounts")
            )
            if not accounts:
                messages.error(request, "Pick at least one connected account to publish to.")
                return redirect("content:compose", pk=pk)
            if _do_publish(request, post, accounts):
                return redirect("content:post_detail", pk=pk)
            return redirect("content:compose", pk=pk)

        messages.success(request, "Saved.")
        return redirect("content:compose", pk=pk)

    return render(request, "content/workbench.html", {
        "p": post,
        "gallery": post.images.all(),
        "styles": IMAGE_STYLES,
        "avatars": Avatar.objects.for_workspace(request.workspace),
        "publish_accounts": SocialAccount.objects.for_workspace(request.workspace).filter(is_active=True),
        "kind_channels_json": json.dumps(uploadpost.KIND_CHANNELS),
        "config": {"text": openrouter.is_configured(), "images": images.is_configured()},
        "tab": "library",
    })


def _add_gallery_image(post, tmp_path, prompt, select=True):
    """Store a temp image file as a new PostImage; optionally select it."""
    pi = PostImage(post=post, prompt=prompt[:500])
    with Path(tmp_path).open("rb") as fh:
        pi.image.save(f"g{post.pk}_{int(timezone.now().timestamp())}.png", File(fh), save=False)
    pi.save()
    if select:
        _select_image(post, pi)
    return pi


def _tile(pi):
    """JSON shape of one gallery image for the client."""
    return {"pk": pi.pk, "url": pi.image.url, "prompt": pi.prompt, "selected": pi.is_selected}


@login_required
@require_POST
def compose_ai(request, pk):
    """The Prompt bar. mode=text writes the caption; mode=image generates a new
    image, or edits references (uploaded refs and/or an `edit_from` gallery image)."""
    post = get_object_or_404(Post, pk=pk, workspace=request.workspace)
    prompt = request.POST.get("prompt", "").strip()
    mode = request.POST.get("mode", "image")
    if not prompt and mode != "image":
        return JsonResponse({"ok": False, "error": "Type a prompt first."})

    # ---- TEXT: write / rewrite the caption or body ----
    if mode == "text":
        if not openrouter.is_configured():
            return JsonResponse({"ok": False, "error": "Writing AI isn't set up (OPENROUTER_API_KEY)."})
        try:
            text = openrouter._chat(CAPTION_SYSTEM, prompt).strip()
        except Exception as e:
            return JsonResponse({"ok": False, "error": f"Writing failed: {e}"})
        post.body = text
        post.save(update_fields=["body"])
        return JsonResponse({"ok": True, "mode": "text", "body": text})

    # ---- IMAGE: generate fresh, or edit from references ----
    if not images.is_configured():
        return JsonResponse({"ok": False, "error": "Image AI isn't set up (FAL_API_KEY)."})

    ref_tmps = []
    for f in request.FILES.getlist("refs"):
        rp = Path(tempfile.gettempdir()) / f"ref_{int(timezone.now().timestamp()*1000)}_{f.name}"
        with rp.open("wb") as out:
            for chunk in f.chunks():
                out.write(chunk)
        ref_tmps.append(rp)

    edit_from = request.POST.get("edit_from")
    if edit_from:
        src = post.images.filter(pk=edit_from).first()
        if src:
            sp = Path(tempfile.gettempdir()) / f"edit_{src.pk}.png"
            with src.image.open("rb") as fh:
                sp.write_bytes(fh.read())
            ref_tmps.insert(0, sp)

    avatar_id = request.POST.get("avatar")
    if avatar_id:
        av = Avatar.objects.filter(pk=avatar_id, workspace=request.workspace).first()
        if av and av.image:
            ap = Path(tempfile.gettempdir()) / f"av_{av.pk}.png"
            with av.image.open("rb") as fh:
                ap.write_bytes(fh.read())
            ref_tmps.append(ap)

    out = Path(tempfile.gettempdir()) / f"gen_{int(timezone.now().timestamp())}.png"
    try:
        if ref_tmps:
            images.edit_image(prompt or "edit this image", ref_tmps, out)
        else:
            style = request.POST.get("style", "design")
            images.generate_image(prompt, out, style=style if style in IMAGE_STYLES else "design")
    except Exception as e:
        return JsonResponse({"ok": False, "error": f"Image failed: {e}"})
    finally:
        for p in ref_tmps:
            p.unlink(missing_ok=True)

    pi = _add_gallery_image(post, out, prompt)
    out.unlink(missing_ok=True)
    return JsonResponse({"ok": True, "mode": "image", "image": _tile(pi)})


@login_required
@require_POST
def gallery_upload(request, pk):
    """＋ tile — the user uploads their own image(s) into the gallery."""
    post = get_object_or_404(Post, pk=pk, workspace=request.workspace)
    files = request.FILES.getlist("images")
    if not files:
        return JsonResponse({"ok": False, "error": "No file chosen."})
    tiles = []
    for f in files:
        pi = PostImage(post=post, prompt="uploaded")
        pi.image.save(f.name, f, save=False)
        pi.save()
        tiles.append(_tile(pi))
    # select the first upload if nothing is selected yet
    if not post.images.filter(is_selected=True).exists():
        _select_image(post, post.images.get(pk=tiles[0]["pk"]))
        tiles[0]["selected"] = True
    return JsonResponse({"ok": True, "images": tiles})


@login_required
@require_POST
def image_select(request, img_pk):
    """Mark a gallery image as the one that publishes."""
    pi = get_object_or_404(PostImage, pk=img_pk, post__workspace=request.workspace)
    _select_image(pi.post, pi)
    return JsonResponse({"ok": True, "pk": pi.pk})


@login_required
@require_POST
def image_delete(request, img_pk):
    """Remove a gallery image; reselect another if we deleted the selected one."""
    pi = get_object_or_404(PostImage, pk=img_pk, post__workspace=request.workspace)
    post, was_selected = pi.post, pi.is_selected
    pi.delete()
    new_selected = None
    if was_selected:
        nxt = post.images.last()
        if nxt:
            _select_image(post, nxt)
            new_selected = nxt.pk
        else:
            post.media = ""
            post.save(update_fields=["media"])
    return JsonResponse({"ok": True, "new_selected": new_selected})


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
        "available_accounts": SocialAccount.objects.for_workspace(request.workspace).filter(
            is_active=True, platform__in=post.available_channels
        ),
        "config": _config(),
    })


@login_required
@require_POST
def publish_post(request, pk):
    """Publish the post to the selected channels via Upload-Post."""
    post = get_object_or_404(Post, pk=pk, workspace=request.workspace)
    accounts = social_publish.accounts_for(
        request.workspace, post.available_channels, request.POST.getlist("accounts")
    )
    if not accounts:
        messages.error(request, "Pick at least one connected account to publish to.")
        return _back(pk)
    _do_publish(request, post, accounts)
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
        messages.success(request, "Publish complete ")
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
