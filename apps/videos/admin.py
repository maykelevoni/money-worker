from django.contrib import admin

from .models import Avatar, TopicIdea, Video


@admin.register(Avatar)
class AvatarAdmin(admin.ModelAdmin):
    list_display = ("name", "is_default", "style", "voice_id", "created_at")
    list_filter = ("is_default",)
    search_fields = ("name",)


@admin.register(Video)
class VideoAdmin(admin.ModelAdmin):
    list_display = ("__str__", "topic_idea", "status", "offer", "created_at")
    list_filter = ("status",)
    search_fields = ("tool_featured", "title", "topic_idea")


@admin.register(TopicIdea)
class TopicIdeaAdmin(admin.ModelAdmin):
    list_display = ("headline", "selected", "created_at")
    list_filter = ("selected",)
    search_fields = ("headline",)
