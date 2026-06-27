from django.contrib import admin

from .models import Post


@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = ("__str__", "kind", "status", "scheduled_at", "created_at")
    list_filter = ("kind", "status")
    search_fields = ("title", "body")
