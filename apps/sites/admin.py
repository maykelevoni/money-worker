from django.contrib import admin

from .models import Page, Website


class PageInline(admin.TabularInline):
    model = Page
    extra = 0
    fields = ("title", "slug", "is_home", "nav_order", "status")


@admin.register(Website)
class WebsiteAdmin(admin.ModelAdmin):
    list_display = ("name", "subdomain", "custom_domain", "status", "workspace")
    list_filter = ("status", "workspace")
    search_fields = ("name", "subdomain", "custom_domain")
    inlines = [PageInline]


@admin.register(Page)
class PageAdmin(admin.ModelAdmin):
    list_display = ("title", "website", "slug", "is_home", "status")
    list_filter = ("status", "website")
    search_fields = ("title", "slug")
