from django.urls import path

from . import views

app_name = "offers"

urlpatterns = [
    path("", views.offer_list, name="list"),
    path("create/", views.offer_create, name="create"),
    path("<int:pk>/manage/", views.offer_manage, name="manage"),
    path("<int:pk>/content/add/", views.content_add, name="content_add"),
    path("<int:pk>/content/<int:content_id>/update/", views.content_update, name="content_update"),
    path("<int:pk>/content/<int:content_id>/delete/", views.content_delete, name="content_delete"),
    path("<int:pk>/modules/add/", views.module_add, name="module_add"),
    path("<int:pk>/modules/<int:module_id>/delete/", views.module_delete, name="module_delete"),
    path("<int:pk>/toggle/", views.offer_toggle, name="toggle"),
    path("<int:pk>/delete/", views.offer_delete, name="delete"),
]
