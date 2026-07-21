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

from .models import Avatar, Video, VideoFind, VideoSearch, VideoSegment
from .services import (
    avatars,
    motion,
    openrouter,
    render as render_svc,
    shorts,
    stt,
    tiktok,
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
    kind = request.POST.get("kind", Video.Kind.SCRIPT_SHORT)
    if kind not in Video.Kind.values:
        kind = Video.Kind.SCRIPT_SHORT
    is_motion = kind == Video.Kind.MOTION_CLIP
    tool = request.POST.get("tool_featured", "").strip()
    # A motion clip needs no subject/topic (there's no script) — just a title.
    if not tool and not is_motion:
        messages.error(request, "Enter a subject/topic for the video.")
        return redirect("videos:factory")
    video = Video.objects.create(
        workspace=request.workspace,
        kind=kind,
        tool_featured=tool,
        title=request.POST.get("title", "").strip(),
        niche=request.POST.get("niche", "").strip(),
        avatar_id=request.POST.get("avatar") or None,
        offer_id=request.POST.get("offer") or None,
        status=Video.Status.DRAFT,
    )
    messages.success(
        request,
        "Motion clip created — upload a reference video to animate your avatar."
        if is_motion else f"Draft created for “{tool}”.",
    )
    return redirect("videos:video_detail", pk=video.pk)


@login_required
@require_POST
def delete_video(request, pk):
    video = get_object_or_404(Video, pk=pk, workspace=request.workspace)
    title = str(video)
    video.delete()
    messages.success(request, f"Deleted “{title}”.")
    return redirect("videos:factory")


# ============================ Research · Viral video search ============================

# Whitelisted sort keys → ORM ordering. "engagement" is a computed property, so it's
# sorted in Python after the fetch.
_FIND_SORTS = {
    "views": "-views",
    "likes": "-likes",
    "comments": "-comments",
    "newest": "-created_at",
    "engagement": None,
}


@login_required
def research_page(request):
    """Viral-video search — the results of the latest TikTok search, sortable/filterable."""
    latest = (
        VideoSearch.objects.for_workspace(request.workspace)
        .order_by("-created_at")
        .first()
    )

    sort = request.GET.get("sort", "views")
    min_views = request.GET.get("min_views", "")

    finds = []
    if latest:
        qs = latest.finds.annotate(video_count=Count("videos", distinct=True))
        if min_views.isdigit():
            qs = qs.filter(views__gte=int(min_views))
        order = _FIND_SORTS.get(sort)
        if order:
            finds = list(qs.order_by(order, "-created_at"))
        else:  # engagement — computed, sort in Python
            finds = sorted(qs, key=lambda f: f.engagement_pct or 0, reverse=True)

    overview = None
    if finds:
        views = [f.views for f in finds]
        overview = {
            "total": len(finds),
            "top_views": max(views),
            "total_views": sum(views),
            "avg_engagement": round(
                sum(f.engagement_pct or 0 for f in finds) / len(finds), 1
            ),
        }

    return render(request, "videos/research.html", {
        "search": latest,
        "finds": finds,
        "overview": overview,
        "config": _config(),
        "tiktok_ready": tiktok.is_available(),
        "tab": "research",
        "filters": {"sort": sort, "min_views": min_views},
        **_pickers(request),
    })


@login_required
@require_POST
def research_run(request):
    """Search TikTok for viral videos on a term (blank = trending) — runs in background."""
    if not tiktok.is_available():
        messages.error(request, "TikTok search isn't installed on the server yet.")
        return redirect("videos:research")
    query = request.POST.get("keyword", "").strip()[:200]
    search = VideoSearch.objects.create(
        workspace=request.workspace, query=query, status="running"
    )
    tiktok.start_search(search, count=24)
    messages.success(request, "Searching TikTok… results appear below in a few seconds.")
    return redirect("videos:research")


@login_required
def research_status(request):
    """Poll the latest search's status so the page knows when to refresh."""
    latest = (
        VideoSearch.objects.for_workspace(request.workspace)
        .order_by("-created_at")
        .first()
    )
    if not latest:
        return JsonResponse({"status": "none"})
    return JsonResponse({
        "status": latest.status,
        "error": latest.error,
        "count": latest.finds.count() if latest.status == "done" else 0,
    })


@login_required
@require_POST
def delete_find(request, pk):
    get_object_or_404(VideoFind, pk=pk, workspace=request.workspace).delete()
    messages.success(request, "Removed from results.")
    return redirect("videos:research")


@login_required
@require_POST
def find_idea(request, pk):
    """Steal the idea: start a script short seeded from the found video's caption."""
    find = get_object_or_404(VideoFind, pk=pk, workspace=request.workspace)
    subject = find.caption[:300] or f"a video by @{find.author_handle}"
    video = Video.objects.create(
        workspace=request.workspace,
        kind=Video.Kind.SCRIPT_SHORT,
        source_find=find,
        topic_idea=subject,
        niche=request.POST.get("niche", "").strip(),
        avatar_id=request.POST.get("avatar") or None,
        offer_id=request.POST.get("offer") or None,
        status=Video.Status.DRAFT,
    )
    try:
        video.talking_points = openrouter.generate_talking_points(
            subject, "", niche=video.niche
        )
        video.save(update_fields=["talking_points"])
    except Exception as e:
        messages.warning(request, f"Video created, but talking points failed: {e}")
    messages.success(request, "Short started from that video's idea.")
    return redirect("videos:video_detail", pk=video.pk)


@login_required
@require_POST
def find_clone(request, pk):
    """Clone the movement: download the found video and seed a Motion Clip with it.

    The download drives the headless browser so it's slow (~10-30s) and blocks this
    request. If it fails, the Motion Clip is still created — the user can upload a
    reference video manually on the next page.
    """
    from django.core.files.base import ContentFile

    find = get_object_or_404(VideoFind, pk=pk, workspace=request.workspace)
    video = Video.objects.create(
        workspace=request.workspace,
        kind=Video.Kind.MOTION_CLIP,
        source_find=find,
        title=(find.caption[:120] or f"Motion from @{find.author_handle}"),
        niche=request.POST.get("niche", "").strip(),
        avatar_id=request.POST.get("avatar") or None,
        offer_id=request.POST.get("offer") or None,
        status=Video.Status.DRAFT,
    )
    try:
        data = tiktok.download(find.url)
        video.motion_ref.save(f"tiktok_{find.tiktok_id}.mp4", ContentFile(data), save=True)
        messages.success(request, "Source video pulled in — now generate the motion clip.")
    except Exception as e:
        messages.warning(
            request,
            f"Motion clip created, but the source download failed ({e}). "
            "Upload a reference video manually on this page.",
        )
    return redirect("videos:video_detail", pk=video.pk)


# ============================ The per-video page ============================

@login_required
def video_detail(request, pk):
    """One video's full page: script, assets, actions — like a post editor.

    Motion clips have a different shape (no script/timeline — just a character + a
    reference video), so they get their own simpler screen.
    """
    video = get_object_or_404(
        Video.objects.select_related("offer", "avatar"), pk=pk, workspace=request.workspace
    )

    if video.kind == Video.Kind.MOTION_CLIP:
        if request.method == "POST":
            video.title = request.POST.get("title", video.title).strip()
            video.caption = request.POST.get("caption", video.caption)
            video.niche = request.POST.get("niche", video.niche).strip()
            video.avatar_id = request.POST.get("avatar") or None
            video.offer_id = request.POST.get("offer") or None
            video.save()
            messages.success(request, "Saved.")
            return redirect("videos:video_detail", pk=video.pk)
        return render(request, "videos/video_motion.html", {
            "v": video,
            "config": _config(),
            "share_accounts": SocialAccount.objects.for_workspace(request.workspace).filter(
                is_active=True, platform__in=uploadpost.KIND_CHANNELS["video"]
            ),
            **_pickers(request),
        })

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


# ============================ Motion Clips ============================

@login_required
@require_POST
def upload_motion_ref(request, pk):
    """Save the reference video whose movement gets mapped onto the avatar."""
    video = get_object_or_404(Video, pk=pk, workspace=request.workspace)
    clip = request.FILES.get("motion_ref")
    if not clip:
        messages.error(request, "Choose a reference video to upload.")
        return _back(pk)
    if not (clip.content_type or "").startswith("video/"):
        messages.error(request, "That doesn't look like a video file.")
        return _back(pk)
    video.motion_ref = clip
    video.save(update_fields=["motion_ref"])
    messages.success(request, "Reference video uploaded — now generate the clip.")
    return _back(pk)


@login_required
@require_POST
def generate_motion(request, pk):
    """Animate the avatar with the uploaded reference motion (runs in the background)."""
    video = get_object_or_404(Video, pk=pk, workspace=request.workspace)
    if not motion.is_configured():
        messages.error(request, "Set FAL_API_KEY to generate motion clips.")
        return _back(pk)
    if not video.motion_ref:
        messages.error(request, "Upload a reference video first.")
        return _back(pk)
    if motion._character_image(video) is None:
        messages.error(request, "Pick an avatar with an image (or give it a full body) first.")
        return _back(pk)
    motion.start_motion(video)
    messages.success(request, "Animating your avatar… watch the progress below.")
    return _back(pk)


@login_required
@require_POST
def avatar_full_body(request, pk):
    """Generate a full-body version of the avatar's portrait (for Motion Clips)."""
    avatar = get_object_or_404(Avatar, pk=pk, workspace=request.workspace)
    try:
        avatars.generate_full_body(avatar)
    except avatars.NotConfigured as e:
        messages.error(request, str(e))
        return redirect("videos:avatars")
    except Exception as e:
        messages.error(request, f"Full-body generation failed: {e}")
        return redirect("videos:avatars")
    messages.success(request, f"Full body created for “{avatar.name}”.")
    return redirect("videos:avatars")


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
