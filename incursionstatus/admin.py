from django.contrib import admin

from .models import Incursion, IncursionChange, IncursionSyncStatus


@admin.register(Incursion)
class IncursionAdmin(admin.ModelAdmin):
    list_display = (
        "constellation_name",
        "constellation_id",
        "state",
        "security_status",
        "influence",
        "has_boss",
        "is_active",
        "last_seen",
    )
    list_filter = ("is_active", "state", "has_boss")
    search_fields = (
        "constellation_name",
        "constellation_id",
        "staging_solar_system_name",
    )
    readonly_fields = ("first_seen", "last_seen", "last_changed", "ended_at")


@admin.register(IncursionChange)
class IncursionChangeAdmin(admin.ModelAdmin):
    list_display = (
        "constellation_label",
        "constellation_id",
        "change_type",
        "observed_at",
    )
    list_filter = ("change_type",)
    search_fields = ("constellation_id",)
    readonly_fields = (
        "incursion",
        "constellation_id",
        "change_type",
        "changed_fields",
        "snapshot",
        "observed_at",
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(IncursionSyncStatus)
class IncursionSyncStatusAdmin(admin.ModelAdmin):
    list_display = ("last_attempt_at", "last_success_at", "last_change_at")
    readonly_fields = (
        "last_attempt_at",
        "last_success_at",
        "last_change_at",
        "last_error",
    )

    def has_add_permission(self, request):
        return not IncursionSyncStatus.objects.exists()
