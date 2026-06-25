from django.urls import path

from . import views

app_name = "sequences"

urlpatterns = [
    path("emails/", views.step_list, name="list"),
    path("emails/create/", views.step_create, name="create"),
    path("emails/starter/", views.load_starter, name="starter"),
    path("emails/<int:pk>/delete/", views.step_delete, name="delete"),
    path("emails/<int:pk>/toggle/", views.step_toggle, name="toggle"),
    path("scheduler/", views.scheduler, name="scheduler"),
    path("automations/", views.automations, name="automations"),
    path("automations/run/", views.run_now, name="run_now"),
]
