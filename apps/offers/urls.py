from django.urls import path

from . import views

app_name = "offers"

urlpatterns = [
    path("", views.offer_list, name="list"),
    path("create/", views.offer_create, name="create"),
    path("<int:pk>/toggle/", views.offer_toggle, name="toggle"),
    path("<int:pk>/delete/", views.offer_delete, name="delete"),
]
