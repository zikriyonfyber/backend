from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import AAASession, IdentityChip, RouterDevice, Subscriber


@admin.register(Subscriber)
class SubscriberAdmin(UserAdmin):
    model = Subscriber
    list_display = ["phone_number", "full_name", "email", "is_active", "date_joined"]
    search_fields = ["phone_number", "full_name", "email"]
    ordering = ["-date_joined"]
    fieldsets = (
        (None, {"fields": ("phone_number", "password")}),
        ("Profile", {"fields": ("full_name", "email", "address")}),
        ("Permissions", {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
        ("Important dates", {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (None, {"classes": ("wide",), "fields": ("phone_number", "full_name", "password1", "password2")}),
    )


@admin.register(IdentityChip)
class IdentityChipAdmin(admin.ModelAdmin):
    list_display = ["chip_id", "subscriber", "status", "balance", "last_seen_at", "last_seen_router"]
    list_filter = ["status"]
    search_fields = ["chip_id", "subscriber__phone_number", "subscriber__full_name"]
    autocomplete_fields = ["subscriber", "last_seen_router"]
    readonly_fields = ["chip_id", "issued_at", "cached_balance_synced_at"]


@admin.register(RouterDevice)
class RouterDeviceAdmin(admin.ModelAdmin):
    list_display = ["serial_number", "mac_address", "is_active", "firmware_version", "last_heartbeat_at"]
    search_fields = ["serial_number", "mac_address", "install_location"]
    readonly_fields = ["api_key_hash"]

    actions = ["issue_new_api_key"]

    @admin.action(description="Issue a new API key (invalidates the old one)")
    def issue_new_api_key(self, request, queryset):
        for router in queryset:
            raw_key = RouterDevice.generate_api_key()
            router.set_api_key(raw_key)
            router.save(update_fields=["api_key_hash"])
            self.message_user(request, f"{router.serial_number}: new key = {raw_key} (copy now, not shown again)")


@admin.register(AAASession)
class AAASessionAdmin(admin.ModelAdmin):
    list_display = ["chip", "router", "status", "client_ip", "started_at", "stopped_at", "total_bytes"]
    list_filter = ["status", "router"]
    search_fields = ["chip__chip_id", "client_ip"]
    date_hierarchy = "started_at"
