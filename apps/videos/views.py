from pathlib import Path

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.offers.models import Offer
from apps.social import publish as social_publish
from apps.social.models import SocialAccount

from .models import Avatar, TopicIdea, Video, VideoSegment
from .services import (
    avatars,
    openrouter,
    render as render_svc,
    research,
    shorts,
    stt,
    trends,
    uploadpost,
    voice,
)


def _config():
    return {
        "openrouter": openrouter.is_configured(),
        "voice": voice.is_configured(),
        "render": render_svc.is_configured(),
        "stt": stt.is_configured(),
        "share": uploadpost.is_configured(),
    }


def _pickers(request):
    ws = request.workspace
    return {
        "offers": Offer.objects.for_workspace(ws).filter(is_active=True),
        "avatars": Avatar.objects.for_workspace(ws),
    }


# ============================ Factory · Videos phase ============================

@login_required
def factory(request):
    """Videos phase — the list of videos; each row opens its own page."""
    videos = Video.objects.for_workspace(request.workspace).select_related("offer", "avatar")
    counts = {
        row["status"]: row["n"]
        for row in videos.values("status").annotate(n=Count("id"))
    }
    return render(request, "videos/videos_list.html", {
        "videos": videos,
        "stats": {
            "total": sum(counts.values()),
            "drafts": counts.get("draft", 0),
            "in_progress": counts.get("scripted", 0) + counts.get("voiced", 0),
            "awaiting": counts.get("rendered", 0),
            "posted": counts.get("posted", 0),
        },
        "config": _config(),
        "tab": "videos",
        **_pickers(request),
    })


@login_required
@require_POST
def create(request):
    """Start a video from a subject directly → land on its page."""
    tool = request.POST.get("tool_featured", "").strip()
    if not tool:
        messages.error(request, "Enter a subject/topic for the video.")
        return redirect("videos:factory")
    video = Video.objects.create(
        workspace=request.workspace,
        tool_featured=tool,
        niche=request.POST.get("niche", "").strip(),
        avatar_id=request.POST.get("avatar") or None,
        offer_id=request.POST.get("offer") or None,
        status=Video.Status.DRAFT,
    )
    messages.success(request, f"Draft created for “{tool}”.")
    return redirect("videos:video_detail", pk=video.pk)


@login_required
@require_POST
def delete_video(request, pk):
    video = get_object_or_404(Video, pk=pk, workspace=request.workspace)
    title = str(video)
    video.delete()
    messages.success(request, f"Deleted “{title}”.")
    return redirect("videos:factory")


# ============================ Research · Topic Explorer ============================

# Whitelisted sort keys → ORM ordering (desc where "more" is more interesting).
_SORTS = {
    "volume": "-search_volume",
    "difficulty": "difficulty",
    "trend": "-trend_pct",
    "newest": "-created_at",
}


@login_required
def research_page(request):
    """Topic Explorer — researched topics with data, in one sortable/filterable list."""
    ideas = (
        TopicIdea.objects.for_workspace(request.workspace)
        .filter(archived=False)
        .annotate(post_count=Count("posts", distinct=True),
                  video_count=Count("videos", distinct=True))
    )

    sort = request.GET.get("sort", "volume")
    min_volume = request.GET.get("min_volume", "")
    max_diff = request.GET.get("max_diff", "")
    trend = request.GET.get("trend", "")
    intent = request.GET.get("intent", "")

    if min_volume.isdigit():
        ideas = ideas.filter(search_volume__gte=int(min_volume))
    if max_diff.isdigit():
        ideas = ideas.filter(difficulty__lte=int(max_diff))
    if trend in {"up", "flat", "down"}:
        ideas = ideas.filter(trend_dir=trend)
    if intent:
        ideas = ideas.filter(intent=intent)
    ideas = list(ideas.order_by(_SORTS.get(sort, "-search_volume"), "-created_at"))

    # Enrich each row for the Ubersuggest-style table: an SEO-difficulty band
    # (colour) and a small momentum sparkline derived from trend direction.
    for idea in ideas:
        d = idea.difficulty
        idea.sd_band = None if d is None else ("easy" if d < 34 else "medium" if d < 67 else "hard")
        idea.spark = _momentum_spark(idea)

    vols = [i.search_volume for i in ideas if i.search_volume is not None]
    diffs = [i.difficulty for i in ideas if i.difficulty is not None]
    overview = {
        "total": len(ideas),
        "avg_volume": round(sum(vols) / len(vols)) if vols else None,
        "avg_difficulty": round(sum(diffs) / len(diffs)) if diffs else None,
        "rising": sum(1 for i in ideas if i.trend_dir == "up"),
    }

    return render(request, "videos/research.html", {
        "ideas": ideas,
        "overview": overview,
        "config": _config(),
        "tab": "research",
        "filters": {"sort": sort, "min_volume": min_volume, "max_diff": max_diff,
                    "trend": trend, "intent": intent},
        "intents": TopicIdea.Intent.choices,
        **_pickers(request),
    })


def _momentum_spark(idea) -> str:
    """A 12-point SVG polyline (viewBox 0 0 60 20) showing momentum direction.

    Derived from trend_dir/trend_pct — it visualises direction, not real monthly
    search history (which we don't store). Deterministic per topic so it's stable.
    """
    n = 12
    slope = {"up": 1, "down": -1}.get(idea.trend_dir, 0)
    amp = min(abs(idea.trend_pct or 0), 60) / 60.0
    seed = (idea.pk * 2654435761) & 0x7FFFFFFF
    pts = []
    for i in range(n):
        seed = (seed * 1103515245 + 12345) & 0x7FFFFFFF
        jitter = (seed / 0x7FFFFFFF - 0.5) * 3.4
        base = 10 - slope * (i - (n - 1) / 2) * (0.55 + amp * 0.9)
        y = max(2.0, min(18.0, base + jitter))
        x = i * (60 / (n - 1))
        pts.append(f"{x:.1f},{y:.1f}")
    return " ".join(pts)


@login_required
@require_POST
def research_run(request):
    """Explore topics around an optional seed/niche → save them with their data."""
    niche = request.POST.get("niche", "").strip()
    seed = request.POST.get("keyword", "").strip()
    try:
        topics = research.explore_topics(seed=seed, niche=niche, n=10)
    except research.NotConfigured as e:
        messages.error(request, str(e))
        return redirect("videos:research")
    except Exception as e:
        messages.error(request, f"Research failed: {e}")
        return redirect("videos:research")
    for t in topics:
        TopicIdea.objects.create(
            workspace=request.workspace,
            headline=t["headline"],
            seed=seed,
            description=t.get("description", ""),
            angle=t.get("angle", ""),
            why_viral=t.get("why_viral", ""),
            search_volume=t.get("search_volume"),
            difficulty=t.get("difficulty"),
            intent=t.get("intent", ""),
            trend_dir=t.get("trend_dir", ""),
            trend_pct=t.get("trend_pct"),
            related=t.get("related", []),
        )
    messages.success(request, f"Explored {len(topics)} topics ")
    return redirect("videos:research")


@login_required
def topic_detail(request, pk):
    """A researched topic in full — description, data, real Google Trends, create."""
    idea = get_object_or_404(
        TopicIdea.objects.annotate(post_count=Count("posts", distinct=True),
                                   video_count=Count("videos", distinct=True)),
        pk=pk, workspace=request.workspace,
    )
    live = trends.interest(idea.headline)  # best-effort; None if Trends unavailable
    return render(request, "videos/topic_detail.html", {
        "idea": idea,
        "live": live,
        "config": _config(),
        "tab": "research",
        **_pickers(request),
    })


@login_required
@require_POST
def delete_idea(request, pk):
    get_object_or_404(TopicIdea, pk=pk, workspace=request.workspace).delete()
    messages.success(request, "Idea deleted.")
    return redirect("videos:research")


@login_required
@require_POST
def pick_idea(request, pk):
    """Turn an idea into a video → land on its page (talking points generated).

    The idea stays in research (reusable) so it can also spawn Studio posts.
    """
    idea = get_object_or_404(TopicIdea, pk=pk, workspace=request.workspace)
    video = Video.objects.create(
        workspace=request.workspace,
        source_idea=idea,
        topic_idea=idea.headline,
        niche=request.POST.get("niche", "").strip(),
        avatar_id=request.POST.get("avatar") or None,
        offer_id=request.POST.get("offer") or None,
        status=Video.Status.DRAFT,
    )
    try:
        video.talking_points = openrouter.generate_talking_points(
            idea.headline, idea.angle, niche=video.niche
        )
        video.save(update_fields=["talking_points"])
    except Exception as e:
        messages.warning(request, f"Video created, but talking points failed: {e}")
    messages.success(request, "Video created from idea ")
    return redirect("videos:video_detail", pk=video.pk)


@login_required
@require_POST
def spawn_post(request, pk):
    """Turn an idea into a Studio post (text / image / article) → open the workbench.

    Pre-seeds the draft from the idea and records provenance; the idea stays in
    research so it can feed more formats.
    """
    from apps.content.models import Post

    idea = get_object_or_404(TopicIdea, pk=pk, workspace=request.workspace)
    kinds = {Post.Kind.TEXT, Post.Kind.IMAGE, Post.Kind.ARTICLE}
    kind = request.POST.get("kind")
    if kind not in kinds:
        messages.error(request, "Unknown content type.")
        return redirect("videos:research")
    post = Post.objects.create(
        workspace=request.workspace,
        kind=kind,
        status=Post.Status.DRAFT,
        source_idea=idea,
        title=idea.headline[:300],
        body=idea.angle or idea.why_viral or "",
    )
    messages.success(request, f"{post.get_kind_display()} started from idea ")
    return redirect("content:compose", pk=post.pk)


@login_required
@require_POST
def archive_idea(request, pk):
    """Clear a used idea out of the research list without deleting its content."""
    idea = get_object_or_404(TopicIdea, pk=pk, workspace=request.workspace)
    idea.archived = True
    idea.save(update_fields=["archived"])
    messages.success(request, "Idea archived.")
    return redirect("videos:research")


# ============================ The per-video page ============================

@login_required
def video_detail(request, pk):
    """One video's full page: script, assets, actions — like a post editor."""
    video = get_object_or_404(
        Video.objects.select_related("offer", "avatar"), pk=pk, workspace=request.workspace
    )
    if request.method == "POST":
        video.title = request.POST.get("title", video.title).strip()
        video.tool_featured = request.POST.get("tool_featured", video.tool_featured).strip()
        video.script = request.POST.get("script", video.script)
        video.caption = request.POST.get("caption", video.caption)
        video.niche = request.POST.get("niche", video.niche).strip()
        video.avatar_id = request.POST.get("avatar") or None
        video.offer_id = request.POST.get("offer") or None
        video.captions = request.POST.get("captions") == "on"
        if video.script and video.status == Video.Status.DRAFT:
            video.status = Video.Status.SCRIPTED
        video.save()
        messages.success(request, "Saved.")
        return redirect("videos:video_detail", pk=video.pk)
    return render(request, "videos/video_detail.html", {
        "v": video,
        "segments": video.segments.all(),
        "config": _config(),
        "share_accounts": SocialAccount.objects.for_workspace(request.workspace).filter(
            is_active=True, platform__in=uploadpost.KIND_CHANNELS["video"]
        ),
        **_pickers(request),
    })


def _back(pk):
    return redirect("videos:video_detail", pk=pk)


@login_required
@require_POST
def upload_audio(request, pk):
    """Save the Portuguese voice memo and transcribe it."""
    video = get_object_or_404(Video, pk=pk, workspace=request.workspace)
    audio = request.FILES.get("audio")
    if not audio:
        messages.error(request, "Choose an audio file to upload.")
        return _back(pk)
    video.source_audio = audio
    video.save(update_fields=["source_audio"])
    try:
        video.transcript_pt = stt.transcribe(video.source_audio.path)
        video.save(update_fields=["transcript_pt"])
    except stt.NotConfigured as e:
        messages.error(request, str(e))
        return _back(pk)
    except Exception as e:
        messages.error(request, f"Transcription failed: {e}")
        return _back(pk)
    messages.success(request, "Audio transcribed  — generate the script next.")
    return _back(pk)


@login_required
@require_POST
def gen_script(request, pk):
    video = get_object_or_404(Video, pk=pk, workspace=request.workspace)
    try:
        if video.transcript_pt:
            data = openrouter.adapt_transcript_to_script(
                video.transcript_pt, video.topic_idea, video.talking_points, niche=video.niche
            )
        elif video.tool_featured or video.topic_idea:
            data = openrouter.generate_script(
                video.tool_featured or video.topic_idea, niche=video.niche
            )
        else:
            messages.error(request, "Add a subject or record your voice memo first.")
            return _back(pk)
    except openrouter.NotConfigured as e:
        messages.error(request, str(e))
        return _back(pk)
    except Exception as e:
        messages.error(request, f"Script generation failed: {e}")
        return _back(pk)
    video.title = data["title"]
    video.hook = data["hook"]
    video.script = data["script"]
    video.caption = data["caption"]
    video.status = Video.Status.SCRIPTED
    video.save()
    messages.success(request, "Script generated ")
    return _back(pk)


@login_required
@require_POST
def gen_voice(request, pk):
    video = get_object_or_404(Video, pk=pk, workspace=request.workspace)
    if not video.script:
        messages.error(request, "Generate or write the script first.")
        return _back(pk)
    try:
        avatar = video.avatar if video.avatar_id else None
        ref = avatar.voice_ref if avatar and avatar.voice_ref else None
        url = voice.generate_voiceover(
            video.script, filename=f"video_{video.pk}.wav", ref_audio=ref
        )
    except voice.NotConfigured as e:
        messages.error(request, str(e))
        return _back(pk)
    except Exception as e:
        messages.error(request, f"Voiceover failed: {e}")
        return _back(pk)
    video.voice_url = url
    video.status = Video.Status.VOICED
    video.save()
    messages.success(request, "Voiceover generated ")
    return _back(pk)


@login_required
@require_POST
def generate_short(request, pk):
    """One click: run the whole pipeline (script→voice→slides→render) in the background."""
    video = get_object_or_404(Video, pk=pk, workspace=request.workspace)
    shorts.start_generation(video)
    messages.success(request, "Generating your short… watch the progress below. ")
    return _back(pk)


@login_required
def short_status(request, pk):
    """JSON progress for the one-click generation, polled by the page."""
    video = get_object_or_404(Video, pk=pk, workspace=request.workspace)
    return JsonResponse({
        "status": video.gen_status,
        "step": video.gen_step,
        "video_url": video.video_url,
    })


@login_required
@require_POST
def gen_scenes(request, pk):
    """Build pause-synced beats from the voiceover and illustrate each with an image."""
    video = get_object_or_404(Video, pk=pk, workspace=request.workspace)
    if not video.voice_url:
        messages.error(request, "Generate the voiceover first.")
        return _back(pk)
    try:
        beats = shorts.build_segments(video)
        made = shorts.illustrate_segments(video)
    except Exception as e:
        messages.error(request, f"Slides failed: {e}")
        return _back(pk)
    messages.success(request, f"Made {made} slides from {beats} beats  — review, then render.")
    return _back(pk)


@login_required
@require_POST
def regen_slide(request, pk, seg_id):
    """Regenerate one beat's image, optionally toggling whether the avatar features."""
    video = get_object_or_404(Video, pk=pk, workspace=request.workspace)
    seg = get_object_or_404(VideoSegment, pk=seg_id, video=video)
    use_avatar = None
    if request.POST.get("toggle_avatar"):
        use_avatar = not seg.uses_avatar
    try:
        shorts.regenerate_segment(video, seg, use_avatar=use_avatar)
    except Exception as e:
        messages.error(request, f"Slide regen failed: {e}")
        return _back(pk)
    messages.success(request, f"Slide {seg.order + 1} regenerated ")
    return _back(pk)


@login_required
@require_POST
def render_video_view(request, pk):
    video = get_object_or_404(Video, pk=pk, workspace=request.workspace)
    try:
        url = render_svc.render_short(video)
    except render_svc.RenderError as e:
        messages.error(request, str(e))
        return _back(pk)
    except Exception as e:
        messages.error(request, f"Render failed: {e}")
        return _back(pk)
    video.video_url = url
    video.status = Video.Status.RENDERED
    video.save()
    messages.success(request, "Short rendered  — review and approve.")
    return _back(pk)


@login_required
@require_POST
def approve(request, pk):
    video = get_object_or_404(Video, pk=pk, workspace=request.workspace)
    video.status = Video.Status.APPROVED
    video.save()
    messages.success(request, "Approved  — download it and post to TikTok.")
    return _back(pk)


@login_required
@require_POST
def mark_posted(request, pk):
    video = get_object_or_404(Video, pk=pk, workspace=request.workspace)
    video.status = Video.Status.POSTED
    video.posted_at = timezone.now()
    video.save()
    messages.success(request, "Marked as posted ")
    return _back(pk)


def _video_file_path(video):
    """Local filesystem path of a video's rendered MP4 from its media URL."""
    rel = video.video_url.replace(settings.MEDIA_URL, "", 1)
    return Path(settings.MEDIA_ROOT) / rel


@login_required
@require_POST
def share_video(request, pk):
    """Publish the rendered video to the chosen platforms via Upload-Post."""
    video = get_object_or_404(Video, pk=pk, workspace=request.workspace)
    accounts = social_publish.accounts_for(
        request.workspace, uploadpost.KIND_CHANNELS["video"], request.POST.getlist("accounts")
    )
    if not accounts:
        messages.error(request, "Pick at least one connected account to share to.")
        return _back(pk)
    if not video.video_url:
        messages.error(request, "Render the video before sharing it.")
        return _back(pk)

    file_path = _video_file_path(video)
    if not file_path.exists():
        messages.error(request, "The rendered file is missing — re-render the video.")
        return _back(pk)

    title = (video.title or str(video)).strip()
    ts = int(timezone.now().timestamp())
    results, last_id, errors = {}, "", []
    for profile, platforms in social_publish.group_by_profile(accounts).items():
        try:
            with file_path.open("rb") as fh:
                r = uploadpost.upload_video(
                    fh, file_path.name, platforms, title, video.caption,
                    user=profile, idempotency_key=f"video-{video.pk}-{profile}-{ts}",
                )
        except uploadpost.NotConfigured as e:
            messages.error(request, str(e))
            return _back(pk)
        except Exception as e:
            errors.append(f"{profile}: {e}")
            continue
        last_id = r.get("request_id", "") or last_id
        if r.get("results"):
            results.update(r["results"])

    video.share_request_id = last_id
    if results:
        video.share_results = results
        video.share_status = "done"
        video.status = Video.Status.POSTED
        video.posted_at = timezone.now()
    elif last_id:
        video.share_status = "pending"
    video.save()

    if errors:
        messages.warning(request, "Some posts failed — " + "; ".join(errors))
    if results or last_id:
        handles = ", ".join(a.handle for a in accounts)
        messages.success(request, f"Sharing to {handles} ")
    return _back(pk)


@login_required
@require_POST
def share_status(request, pk):
    """Poll Upload-Post for the result of an in-flight share."""
    video = get_object_or_404(Video, pk=pk, workspace=request.workspace)
    if not video.share_request_id:
        messages.error(request, "No share in progress for this video.")
        return _back(pk)
    try:
        data = uploadpost.check_status(video.share_request_id)
    except uploadpost.NotConfigured as e:
        messages.error(request, str(e))
        return _back(pk)
    except Exception as e:
        messages.error(request, f"Status check failed: {e}")
        return _back(pk)

    results = data.get("results") or {}
    if results:
        video.share_results = results
    # Treat an explicit completion flag, or the presence of results, as done.
    if data.get("status") in ("completed", "done") or results:
        video.share_status = "done"
        if video.status != Video.Status.POSTED:
            video.status = Video.Status.POSTED
            video.posted_at = timezone.now()
        messages.success(request, "Share complete ")
    else:
        messages.success(request, "Still processing — check again in a moment.")
    video.save()
    return _back(pk)


# ============================ Factory · Avatars ============================

@login_required
def avatar_list(request):
    return render(request, "videos/avatars.html", {
        "avatars": Avatar.objects.for_workspace(request.workspace),
        "configured": avatars.is_configured(),
        "tab": "avatars",
    })


def _save_reference_uploads(files):
    """Write uploaded reference images to temp files; return their paths (for edit_image)."""
    import tempfile

    paths = []
    for f in files or []:
        if not getattr(f, "content_type", "").startswith("image/"):
            continue
        suffix = Path(f.name).suffix or ".png"
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
        for chunk in f.chunks():
            tmp.write(chunk)
        tmp.close()
        paths.append(Path(tmp.name))
    return paths


def _cleanup_paths(paths):
    for p in paths or []:
        try:
            Path(p).unlink(missing_ok=True)
        except OSError:
            pass


@login_required
@require_POST
def avatar_create(request):
    name = request.POST.get("name", "").strip()
    appearance = request.POST.get("appearance", "").strip()
    if not name or not appearance:
        messages.error(request, "Give your influencer a name and describe how they look.")
        return redirect("videos:avatars")
    seed = request.POST.get("seed", "").strip()
    style = request.POST.get("style", "").strip()
    avatar = Avatar.objects.create(
        workspace=request.workspace,
        name=name, appearance=appearance, style=style,
        seed=int(seed) if seed.isdigit() else None,
    )
    # Optional reference images (a photo, a cartoon, an inspiration) → based-on look.
    ref_paths = _save_reference_uploads(request.FILES.getlist("refs"))
    try:
        avatars.generate_portrait(avatar, reference_paths=ref_paths)
    except avatars.NotConfigured as e:
        messages.error(request, str(e))
        return redirect("videos:avatars")
    except Exception as e:
        messages.error(request, f"Influencer image failed: {e}")
        return redirect("videos:avatars")
    finally:
        _cleanup_paths(ref_paths)
    messages.success(request, f"Avatar “{name}” created ")
    # First-run flow: creating your influencer completes step 1 → go to the composer.
    ws = request.workspace
    if ws and not ws.onboarding_done and ws.onboarding_step == 0:
        ws.advance_onboarding(1)  # STEP_POST
        return redirect("onboarding:start")
    return redirect("videos:avatars")


@login_required
@require_POST
def avatar_regenerate(request, pk):
    avatar = get_object_or_404(Avatar, pk=pk, workspace=request.workspace)
    try:
        avatars.generate_portrait(avatar)
    except avatars.NotConfigured as e:
        messages.error(request, str(e))
        return redirect("videos:avatars")
    except Exception as e:
        messages.error(request, f"Regenerate failed: {e}")
        return redirect("videos:avatars")
    messages.success(request, f"“{avatar.name}” regenerated.")
    return redirect("videos:avatars")


@login_required
@require_POST
def avatar_voice(request, pk):
    """Upload the voice-cloning reference clip for this avatar (F5-TTS clones from it)."""
    avatar = get_object_or_404(Avatar, pk=pk, workspace=request.workspace)
    clip = request.FILES.get("voice")
    if not clip:
        messages.error(request, "Choose an audio file first.")
        return redirect("videos:avatars")
    avatar.voice_ref = clip
    avatar.save(update_fields=["voice_ref"])
    messages.success(request, f"Voice sample saved for “{avatar.name}”  — you can generate voiceovers now.")
    return redirect("videos:avatars")
