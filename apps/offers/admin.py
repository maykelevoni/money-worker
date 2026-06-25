from django.contrib import admin

from .models import Offer


@admin.register(Offer)
class OfferAdmin(admin.ModelAdmin):
    list_display = ("name", "vendor", "commission", "is_recurring", "is_active")
    list_filter = ("is_recurring", "is_active")
    search_fields = ("name", "vendor")
