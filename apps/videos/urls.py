from django.urls import path

from . import views

app_name = "videos"

urlpatterns = [
    path("", views.factory, name="factory"),
    path("research/", views.research_ideas, name="research"),
    path("idea/<int:pk>/pick/", views.pick_idea, name="pick_idea"),
    path("create/", views.create, name="create"),
    path("<int:pk>/audio/", views.upload_audio, name="upload_audio"),
    path("<int:pk>/script/", views.gen_script, name="gen_script"),
    path("<int:pk>/voice/", views.gen_voice, name="gen_voice"),
    path("<int:pk>/render/", views.render_video_view, name="render"),
    path("<int:pk>/approve/", views.approve, name="approve"),
    path("<int:pk>/posted/", views.mark_posted, name="mark_posted"),
]
