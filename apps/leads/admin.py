from django.contrib import admin

from .models import CapturePage, Lead


@admin.register(CapturePage)
class CapturePageAdmin(admin.ModelAdmin):
    list_display = ("title", "slug", "lead_magnet", "offer", "is_active", "created_at")
    list_filter = ("is_active",)
    search_fields = ("title", "slug", "headline")
    prepopulated_fields = {"slug": ("title",)}


@admin.register(Lead)
class LeadAdmin(admin.ModelAdmin):
    list_display = ("email", "stage", "lead_magnet", "source_page", "source_video", "created_at")
    list_filter = ("stage",)
    search_fields = ("email",)
