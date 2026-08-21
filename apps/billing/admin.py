from django.contrib import admin

from .models import DailyUsageSummary, Plan, RechargeTransaction, Subscription


@admin.register(Plan)
class PlanAdmin(admin.ModelAdmin):
    list_display = ["name", "cycle", "price", "data_cap_mb", "is_subsidized", "is_active"]
    list_filter = ["cycle", "is_subsidized", "is_active"]
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ["chip", "plan", "status", "expires_at", "data_used_mb"]
    list_filter = ["status", "plan"]
    search_fields = ["chip__chip_id"]
    date_hierarchy = "started_at"


@admin.register(RechargeTransaction)
class RechargeTransactionAdmin(admin.ModelAdmin):
    list_display = ["chip", "plan", "amount", "channel", "created_at"]
    list_filter = ["channel"]
    search_fields = ["chip__chip_id", "reference"]
    date_hierarchy = "created_at"


@admin.register(DailyUsageSummary)
class DailyUsageSummaryAdmin(admin.ModelAdmin):
    list_display = ["chip", "date", "bytes_uploaded", "bytes_downloaded", "session_count"]
    date_hierarchy = "date"
    search_fields = ["chip__chip_id"]
