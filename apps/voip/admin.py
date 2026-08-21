from django.contrib import admin

from .models import CallRecord, SIPNumber


@admin.register(SIPNumber)
class SIPNumberAdmin(admin.ModelAdmin):
    list_display = ["number", "chip", "is_active", "pstn_breakout_enabled", "created_at"]
    search_fields = ["number", "chip__chip_id"]
    readonly_fields = ["sip_password"]


@admin.register(CallRecord)
class CallRecordAdmin(admin.ModelAdmin):
    list_display = [
        "call_id", "caller", "callee_number", "direction", "status",
        "started_at", "duration_seconds", "billed_amount",
    ]
    list_filter = ["direction", "status"]
    search_fields = ["call_id", "caller__number", "callee_number"]
    date_hierarchy = "started_at"
