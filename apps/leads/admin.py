from django.contrib import admin

from .models import Lead


@admin.register(Lead)
class LeadAdmin(admin.ModelAdmin):
    list_display = ("email", "stage", "lead_magnet", "source_video", "created_at")
    list_filter = ("stage",)
    search_fields = ("email",)
