from django.urls import path

from . import views

app_name = "social"

urlpatterns = [
    path("", views.account_list, name="list"),
    path("add/", views.account_create, name="create"),
    path("<int:pk>/toggle/", views.account_toggle, name="toggle"),
    path("<int:pk>/delete/", views.account_delete, name="delete"),
]
