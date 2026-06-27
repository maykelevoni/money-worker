from django.urls import path

from . import views

app_name = "videos"

urlpatterns = [
    # Videos phase (default Factory landing)
    path("", views.factory, name="factory"),
    path("create/", views.create, name="create"),
    # Research phase
    path("research/", views.research_page, name="research"),
    path("research/run/", views.research_run, name="research_run"),
    path("idea/<int:pk>/pick/", views.pick_idea, name="pick_idea"),
    path("idea/<int:pk>/delete/", views.delete_idea, name="delete_idea"),
    # Per-video page + its workflow actions
    path("video/<int:pk>/", views.video_detail, name="video_detail"),
    path("video/<int:pk>/delete/", views.delete_video, name="delete_video"),
    path("video/<int:pk>/audio/", views.upload_audio, name="upload_audio"),
    path("video/<int:pk>/script/", views.gen_script, name="gen_script"),
    path("video/<int:pk>/voice/", views.gen_voice, name="gen_voice"),
    path("video/<int:pk>/render/", views.render_video_view, name="render"),
    path("video/<int:pk>/approve/", views.approve, name="approve"),
    path("video/<int:pk>/posted/", views.mark_posted, name="mark_posted"),
    path("video/<int:pk>/share/", views.share_video, name="share_video"),
    path("video/<int:pk>/share/status/", views.share_status, name="share_status"),
    # Avatars (Factory tab)
    path("avatars/", views.avatar_list, name="avatars"),
    path("avatars/create/", views.avatar_create, name="avatar_create"),
    path("avatars/<int:pk>/regenerate/", views.avatar_regenerate, name="avatar_regenerate"),
]
