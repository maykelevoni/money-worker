from django.contrib import admin

from .models import Avatar, TopicIdea, Video, VideoFind, VideoSearch, VideoSegment


@admin.register(Avatar)
class AvatarAdmin(admin.ModelAdmin):
    list_display = ("name", "is_default", "style", "voice_ref", "created_at")
    list_filter = ("is_default",)
    search_fields = ("name",)


class VideoSegmentInline(admin.TabularInline):
    model = VideoSegment
    extra = 0
    fields = ("order", "text", "start", "end", "uses_avatar", "image")
    ordering = ("order",)


@admin.register(Video)
class VideoAdmin(admin.ModelAdmin):
    list_display = ("__str__", "topic_idea", "status", "offer", "created_at")
    list_filter = ("status",)
    search_fields = ("tool_featured", "title", "topic_idea")
    inlines = [VideoSegmentInline]


@admin.register(TopicIdea)
class TopicIdeaAdmin(admin.ModelAdmin):
    list_display = ("headline", "selected", "created_at")
    list_filter = ("selected",)
    search_fields = ("headline",)


class VideoFindInline(admin.TabularInline):
    model = VideoFind
    extra = 0
    fields = ("author_handle", "caption", "views", "likes", "comments")
    readonly_fields = fields


@admin.register(VideoSearch)
class VideoSearchAdmin(admin.ModelAdmin):
    list_display = ("__str__", "status", "created_at")
    list_filter = ("status",)
    inlines = [VideoFindInline]


@admin.register(VideoFind)
class VideoFindAdmin(admin.ModelAdmin):
    list_display = ("author_handle", "caption", "views", "likes", "created_at")
    search_fields = ("author_handle", "caption")
