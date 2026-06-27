from pathlib import Path

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.offers.models import Offer

from .models import Avatar, TopicIdea, Video
from .services import avatars, openrouter, research, stt, talking, uploadpost, voice


def _config():
    return {
        "openrouter": openrouter.is_configured(),
        "voice": voice.is_configured(),
        "render": talking.is_configured(),
        "stt": stt.is_configured(),
        "share": uploadpost.is_configured(),
    }


def _pickers():
    return {
        "offers": Offer.objects.filter(is_active=True),
        "avatars": Avatar.objects.all(),
    }


# ============================ Factory · Videos phase ============================

@login_required
def factory(request):
    """Videos phase — the list of videos; each row opens its own page."""
    videos = Video.objects.select_related("offer", "avatar").all()
    counts = {
        row["status"]: row["n"]
        for row in Video.objects.values("status").annotate(n=Count("id"))
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
        **_pickers(),
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
    video = get_object_or_404(Video, pk=pk)
    title = str(video)
    video.delete()
    messages.success(request, f"Deleted “{title}”.")
    return redirect("videos:factory")


# ============================ Factory · Research phase ============================

@login_required
def research_page(request):
    """Research phase — trending ideas; they persist and each is deletable."""
    return render(request, "videos/research.html", {
        "ideas": TopicIdea.objects.filter(selected=False),
        "config": _config(),
        "tab": "research",
        **_pickers(),
    })


@login_required
@require_POST
def research_run(request):
    niche = request.POST.get("niche", "").strip()
    keyword = request.POST.get("keyword", "").strip()
    try:
        ideas = research.find_trending_topics(n=5, niche=niche, keyword=keyword)
    except research.NotConfigured as e:
        messages.error(request, str(e))
        return redirect("videos:research")
    except Exception as e:
        messages.error(request, f"Research failed: {e}")
        return redirect("videos:research")
    for idea in ideas:
        TopicIdea.objects.create(
            headline=idea["headline"],
            why_viral=idea.get("why_viral", ""),
            angle=idea.get("angle", ""),
        )
    messages.success(request, f"Found {len(ideas)} trending ideas 🔎")
    return redirect("videos:research")


@login_required
@require_POST
def delete_idea(request, pk):
    get_object_or_404(TopicIdea, pk=pk).delete()
    messages.success(request, "Idea deleted.")
    return redirect("videos:research")


@login_required
@require_POST
def pick_idea(request, pk):
    """Turn an idea into a video → land on its page (talking points generated)."""
    idea = get_object_or_404(TopicIdea, pk=pk)
    video = Video.objects.create(
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
    idea.selected = True
    idea.save(update_fields=["selected"])
    messages.success(request, "Video created from idea 🎯")
    return redirect("videos:video_detail", pk=video.pk)


# ============================ The per-video page ============================

@login_required
def video_detail(request, pk):
    """One video's full page: script, assets, actions — like a post editor."""
    video = get_object_or_404(Video.objects.select_related("offer", "avatar"), pk=pk)
    if request.method == "POST":
        video.title = request.POST.get("title", video.title).strip()
        video.script = request.POST.get("script", video.script)
        video.caption = request.POST.get("caption", video.caption)
        video.niche = request.POST.get("niche", video.niche).strip()
        video.avatar_id = request.POST.get("avatar") or None
        video.offer_id = request.POST.get("offer") or None
        if video.script and video.status == Video.Status.DRAFT:
            video.status = Video.Status.SCRIPTED
        video.save()
        messages.success(request, "Saved.")
        return redirect("videos:video_detail", pk=video.pk)
    return render(request, "videos/video_detail.html", {
        "v": video,
        "config": _config(),
        "share_platforms": uploadpost.PLATFORM_LABELS,
        **_pickers(),
    })


def _back(pk):
    return redirect("videos:video_detail", pk=pk)


@login_required
@require_POST
def upload_audio(request, pk):
    """Save the Portuguese voice memo and transcribe it."""
    video = get_object_or_404(Video, pk=pk)
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
    messages.success(request, "Audio transcribed 📝 — generate the script next.")
    return _back(pk)


@login_required
@require_POST
def gen_script(request, pk):
    video = get_object_or_404(Video, pk=pk)
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
    messages.success(request, "Script generated ✍️")
    return _back(pk)


@login_required
@require_POST
def gen_voice(request, pk):
    video = get_object_or_404(Video, pk=pk)
    if not video.script:
        messages.error(request, "Generate or write the script first.")
        return _back(pk)
    try:
        voice_id = video.avatar.voice_id if video.avatar_id and video.avatar else ""
        url = voice.generate_voiceover(
            video.script, filename=f"video_{video.pk}.mp3", voice_id=voice_id
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
    messages.success(request, "Voiceover generated 🎙️")
    return _back(pk)


@login_required
@require_POST
def render_video_view(request, pk):
    video = get_object_or_404(Video, pk=pk)
    try:
        url = talking.render_video(video)
    except talking.NotConfigured as e:
        messages.error(request, str(e))
        return _back(pk)
    except Exception as e:
        messages.error(request, f"Render failed: {e}")
        return _back(pk)
    video.video_url = url
    video.status = Video.Status.RENDERED
    video.save()
    messages.success(request, "Talking video rendered 🎬 — review and approve.")
    return _back(pk)


@login_required
@require_POST
def approve(request, pk):
    video = get_object_or_404(Video, pk=pk)
    video.status = Video.Status.APPROVED
    video.save()
    messages.success(request, "Approved ✅ — download it and post to TikTok.")
    return _back(pk)


@login_required
@require_POST
def mark_posted(request, pk):
    video = get_object_or_404(Video, pk=pk)
    video.status = Video.Status.POSTED
    video.posted_at = timezone.now()
    video.save()
    messages.success(request, "Marked as posted 📲")
    return _back(pk)


def _video_file_path(video):
    """Local filesystem path of a video's rendered MP4 from its media URL."""
    rel = video.video_url.replace(settings.MEDIA_URL, "", 1)
    return Path(settings.MEDIA_ROOT) / rel


@login_required
@require_POST
def share_video(request, pk):
    """Publish the rendered video to the chosen platforms via Upload-Post."""
    video = get_object_or_404(Video, pk=pk)
    platforms = [p for p in request.POST.getlist("platforms") if p in uploadpost.PLATFORMS]
    if not platforms:
        messages.error(request, "Pick at least one platform to share to.")
        return _back(pk)
    if not video.video_url:
        messages.error(request, "Render the video before sharing it.")
        return _back(pk)

    file_path = _video_file_path(video)
    if not file_path.exists():
        messages.error(request, "The rendered file is missing — re-render the video.")
        return _back(pk)
    title = (video.title or str(video)).strip()
    try:
        with file_path.open("rb") as fh:
            result = uploadpost.upload_video(
                fh, file_path.name, platforms, title, video.caption,
                idempotency_key=f"video-{video.pk}-{int(timezone.now().timestamp())}",
            )
    except uploadpost.NotConfigured as e:
        messages.error(request, str(e))
        return _back(pk)
    except Exception as e:
        messages.error(request, f"Share failed: {e}")
        return _back(pk)

    video.share_request_id = result.get("request_id", "")
    if result.get("results"):
        # Finished synchronously.
        video.share_results = result["results"]
        video.share_status = "done"
        video.status = Video.Status.POSTED
        video.posted_at = timezone.now()
    else:
        video.share_status = "pending"
    video.save()

    labels = ", ".join(uploadpost.PLATFORM_LABELS[p] for p in platforms)
    messages.success(request, f"Sharing to {labels} 🚀")
    return _back(pk)


@login_required
@require_POST
def share_status(request, pk):
    """Poll Upload-Post for the result of an in-flight share."""
    video = get_object_or_404(Video, pk=pk)
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
        messages.success(request, "Share complete ✅")
    else:
        messages.success(request, "Still processing — check again in a moment.")
    video.save()
    return _back(pk)


# ============================ Factory · Avatars ============================

@login_required
def avatar_list(request):
    return render(request, "videos/avatars.html", {
        "avatars": Avatar.objects.all(),
        "configured": avatars.is_configured(),
        "tab": "avatars",
    })


@login_required
@require_POST
def avatar_create(request):
    name = request.POST.get("name", "").strip()
    appearance = request.POST.get("appearance", "").strip()
    if not name or not appearance:
        messages.error(request, "Give the avatar a name and describe how it looks.")
        return redirect("videos:avatars")
    seed = request.POST.get("seed", "").strip()
    avatar = Avatar.objects.create(
        name=name, appearance=appearance, seed=int(seed) if seed.isdigit() else None
    )
    try:
        avatars.generate_portrait(avatar)
    except avatars.NotConfigured as e:
        messages.error(request, str(e))
        return redirect("videos:avatars")
    except Exception as e:
        messages.error(request, f"Avatar image failed: {e}")
        return redirect("videos:avatars")
    messages.success(request, f"Avatar “{name}” created 🎭")
    return redirect("videos:avatars")


@login_required
@require_POST
def avatar_regenerate(request, pk):
    avatar = get_object_or_404(Avatar, pk=pk)
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
