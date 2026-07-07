from django.contrib import admin

from .models import SocialAccount


@admin.register(SocialAccount)
class SocialAccountAdmin(admin.ModelAdmin):
    list_display = ("handle", "platform", "up_profile", "status", "is_active", "workspace")
    list_filter = ("platform", "status", "is_active", "workspace")
    search_fields = ("handle", "display_name", "up_profile")
