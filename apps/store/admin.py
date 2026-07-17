from django.contrib import admin

from .models import Customer, Entitlement, LoginToken


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ("email", "name", "workspace", "created_at")
    search_fields = ("email", "name")


@admin.register(Entitlement)
class EntitlementAdmin(admin.ModelAdmin):
    list_display = ("customer", "offer", "access_type", "status", "current_period_end")
    list_filter = ("status", "access_type")
    search_fields = ("customer__email", "offer__name")


admin.site.register(LoginToken)
