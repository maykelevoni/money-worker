from django.urls import path

from . import views

app_name = "content"

urlpatterns = [
    path("", views.library, name="library"),
    path("calendar/", views.calendar, name="calendar"),
    path("image/", views.image_studio, name="image_studio"),
    path("new/", views.create, name="create"),
    path("<int:pk>/compose/", views.compose, name="compose"),
    path("<int:pk>/ai/", views.compose_ai, name="compose_ai"),
    path("<int:pk>/", views.post_detail, name="post_detail"),
    path("<int:pk>/publish/", views.publish_post, name="publish_post"),
    path("<int:pk>/status/", views.post_status, name="post_status"),
    path("<int:pk>/delete/", views.delete_post, name="delete_post"),
]
