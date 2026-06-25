from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.offers.models import Offer

from .models import Avatar, TopicIdea, Video
from .services import avatars, openrouter, research, stt, talking, voice


@login_required
def avatar_list(request):
    """Avatars section (part of the Video Factory): the reusable character library."""
    return render(
        request,
        "videos/avatars.html",
        {"avatars": Avatar.objects.all(), "configured": avatars.is_configured()},
    )


@login_required
@require_POST
def avatar_create(request):
    """Create a new character and generate its portrait from an appearance prompt."""
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
    """Re-roll the portrait (same prompt + seed) for an existing character."""
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


@login_required
def factory(request):
    """The Video Factory: research ideas → pick → talk → record → adapt → render."""
    videos = Video.objects.select_related("offer", "avatar").all()
    counts = {
        row["status"]: row["n"]
        for row in Video.objects.values("status").annotate(n=Count("id"))
    }
    context = {
        "videos": videos,
        "stats": {
            "total": sum(counts.values()),
            "drafts": counts.get("draft", 0),
            "in_progress": counts.get("scripted", 0) + counts.get("voiced", 0),
            "awaiting": counts.get("rendered", 0),
            "posted": counts.get("posted", 0),
        },
        "ideas": TopicIdea.objects.filter(selected=False),
        "offers": Offer.objects.filter(is_active=True),
        "avatars": Avatar.objects.all(),
        "config": {
            "openrouter": openrouter.is_configured(),
            "voice": voice.is_configured(),
            "render": talking.is_configured(),
            "stt": stt.is_configured(),
        },
    }
    return render(request, "videos/factory.html", context)


@login_required
@require_POST
def research_ideas(request):
    """Step 1: ask an online LLM for trending topic ideas in our niche."""
    keyword = request.POST.get("keyword", "").strip()
    niche = request.POST.get("niche", "").strip()
    try:
        ideas = research.find_trending_topics(n=5, niche=niche, keyword=keyword)
    except research.NotConfigured as e:
        messages.error(request, str(e))
        return redirect("videos:factory")
    except Exception as e:
        messages.error(request, f"Research failed: {e}")
        return redirect("videos:factory")
    for idea in ideas:
        TopicIdea.objects.create(
            headline=idea["headline"],
            why_viral=idea.get("why_viral", ""),
            angle=idea.get("angle", ""),
        )
    messages.success(request, f"Found {len(ideas)} trending ideas 🔎 — pick one.")
    return redirect("videos:factory")


@login_required
@require_POST
def pick_idea(request, pk):
    """Step 2: turn a researched idea into a draft Video + suggest talking points."""
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
        messages.warning(request, f"Idea picked, but talking points failed: {e}")
    idea.selected = True
    idea.save(update_fields=["selected"])
    messages.success(
        request, "Idea picked 🎯 — review the talking points, then record your take."
    )
    return redirect("videos:factory")


@login_required
@require_POST
def upload_audio(request, pk):
    """Step 4: save Mayke's Portuguese voice memo and transcribe it (PT)."""
    video = get_object_or_404(Video, pk=pk)
    audio = request.FILES.get("audio")
    if not audio:
        messages.error(request, "Choose an audio file to upload.")
        return redirect("videos:factory")
    video.source_audio = audio
    video.save(update_fields=["source_audio"])
    try:
        video.transcript_pt = stt.transcribe(video.source_audio.path)
        video.save(update_fields=["transcript_pt"])
    except stt.NotConfigured as e:
        messages.error(request, str(e))
        return redirect("videos:factory")
    except Exception as e:
        messages.error(request, f"Transcription failed: {e}")
        return redirect("videos:factory")
    messages.success(request, "Audio transcribed 📝 — now generate the adapted script.")
    return redirect("videos:factory")


@login_required
@require_POST
def create(request):
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
    messages.success(request, f"Created draft for “{tool}”. Generate the script next.")
    return redirect("videos:factory")


@login_required
@require_POST
def gen_script(request, pk):
    video = get_object_or_404(Video, pk=pk)
    try:
        if video.transcript_pt:
            # New flow: translate + adapt Mayke's own Portuguese take.
            data = openrouter.adapt_transcript_to_script(
                video.transcript_pt,
                video.topic_idea,
                video.talking_points,
                niche=video.niche,
            )
        elif video.tool_featured:
            # Fallback: generate a script straight from the subject.
            data = openrouter.generate_script(video.tool_featured, niche=video.niche)
        else:
            messages.error(
                request,
                "Record + transcribe your voice memo first (or set a subject to feature).",
            )
            return redirect("videos:factory")
    except openrouter.NotConfigured as e:
        messages.error(request, str(e))
        return redirect("videos:factory")
    except Exception as e:  # network/parse errors
        messages.error(request, f"Script generation failed: {e}")
        return redirect("videos:factory")
    video.title = data["title"]
    video.hook = data["hook"]
    video.script = data["script"]
    video.caption = data["caption"]
    video.status = Video.Status.SCRIPTED
    video.save()
    messages.success(request, "Script generated ✍️")
    return redirect("videos:factory")


@login_required
@require_POST
def gen_voice(request, pk):
    video = get_object_or_404(Video, pk=pk)
    if not video.script:
        messages.error(request, "Generate the script first.")
        return redirect("videos:factory")
    try:
        voice_id = video.avatar.voice_id if video.avatar_id and video.avatar else ""
        url = voice.generate_voiceover(
            video.script, filename=f"video_{video.pk}.mp3", voice_id=voice_id
        )
    except voice.NotConfigured as e:
        messages.error(request, str(e))
        return redirect("videos:factory")
    except Exception as e:
        messages.error(request, f"Voiceover failed: {e}")
        return redirect("videos:factory")
    video.voice_url = url
    video.status = Video.Status.VOICED
    video.save()
    messages.success(request, "Voiceover generated 🎙️")
    return redirect("videos:factory")


@login_required
@require_POST
def render_video_view(request, pk):
    video = get_object_or_404(Video, pk=pk)
    try:
        url = talking.render_video(video)
    except talking.NotConfigured as e:
        messages.error(request, str(e))
        return redirect("videos:factory")
    except Exception as e:
        messages.error(request, f"Render failed: {e}")
        return redirect("videos:factory")
    video.video_url = url
    video.status = Video.Status.RENDERED
    video.save()
    messages.success(request, "Talking video rendered 🎬 — review and approve.")
    return redirect("videos:factory")


@login_required
@require_POST
def approve(request, pk):
    video = get_object_or_404(Video, pk=pk)
    video.status = Video.Status.APPROVED
    video.save()
    messages.success(request, "Approved ✅ — download it and post to TikTok.")
    return redirect("videos:factory")


@login_required
@require_POST
def mark_posted(request, pk):
    video = get_object_or_404(Video, pk=pk)
    video.status = Video.Status.POSTED
    video.posted_at = timezone.now()
    video.save()
    messages.success(request, "Marked as posted 📲")
    return redirect("videos:factory")
