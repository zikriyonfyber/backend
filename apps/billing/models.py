"""
apps.billing — plans, active subscriptions, recharges, and usage tracking.

Important non-profit-ISP nuance: data/internet access is gated by an
active Subscription, but *on-network VoIP calling is never gated here* —
see apps.voip, which checks IdentityChip existence only, independent of
Subscription status. That's enforced at the SIP-routing layer, not here.
"""
import uuid

from django.db import models
from django.utils import timezone

from apps.accounts.models import IdentityChip


class Plan(models.Model):
    """A purchasable data plan, branded under Zikriyon Fyber."""

    CYCLE_DAILY = "daily"
    CYCLE_WEEKLY = "weekly"
    CYCLE_MONTHLY = "monthly"
    CYCLE_CHOICES = [
        (CYCLE_DAILY, "Daily"),
        (CYCLE_WEEKLY, "Weekly"),
        (CYCLE_MONTHLY, "Monthly"),
    ]

    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True)
    description = models.TextField(blank=True)
    price = models.DecimalField(max_digits=8, decimal_places=2)
    cycle = models.CharField(max_length=10, choices=CYCLE_CHOICES, default=CYCLE_MONTHLY)
    data_cap_mb = models.PositiveIntegerField(
        null=True, blank=True, help_text="Null = unlimited within the cycle."
    )
    download_speed_mbps = models.PositiveIntegerField(default=10)
    upload_speed_mbps = models.PositiveIntegerField(default=5)
    is_active = models.BooleanField(default=True)
    is_subsidized = models.BooleanField(
        default=False, help_text="Non-profit subsidy plan (reduced/zero price for verified low-income households)."
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["price"]

    def __str__(self):
        return f"{self.name} ({self.get_cycle_display()}, {self.price})"

    def cycle_timedelta(self):
        from datetime import timedelta
        return {
            self.CYCLE_DAILY: timedelta(days=1),
            self.CYCLE_WEEKLY: timedelta(days=7),
            self.CYCLE_MONTHLY: timedelta(days=30),
        }[self.cycle]


class Subscription(models.Model):
    """The chip's currently active (or most recent) plan enrollment."""

    STATUS_ACTIVE = "active"
    STATUS_EXPIRED = "expired"
    STATUS_SUSPENDED = "suspended"
    STATUS_CHOICES = [
        (STATUS_ACTIVE, "Active"),
        (STATUS_EXPIRED, "Expired"),
        (STATUS_SUSPENDED, "Suspended"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    chip = models.ForeignKey(IdentityChip, on_delete=models.CASCADE, related_name="subscriptions")
    plan = models.ForeignKey(Plan, on_delete=models.PROTECT, related_name="subscriptions")
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=STATUS_ACTIVE)

    started_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    data_used_mb = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    class Meta:
        indexes = [
            models.Index(fields=["chip", "status"]),
            models.Index(fields=["expires_at"]),
        ]
        ordering = ["-started_at"]

    def __str__(self):
        return f"{self.chip_id} -> {self.plan.name} ({self.status})"

    def save(self, *args, **kwargs):
        if not self.expires_at:
            self.expires_at = timezone.now() + self.plan.cycle_timedelta()
        super().save(*args, **kwargs)

    @property
    def is_currently_valid(self) -> bool:
        return (
            self.status == self.STATUS_ACTIVE
            and self.expires_at > timezone.now()
            and (self.plan.data_cap_mb is None or self.data_used_mb < self.plan.data_cap_mb)
        )

    def register_usage(self, mb_used):
        self.data_used_mb = models.F("data_used_mb") + mb_used
        self.save(update_fields=["data_used_mb"])
        self.refresh_from_db(fields=["data_used_mb"])
        if self.plan.data_cap_mb is not None and self.data_used_mb >= self.plan.data_cap_mb:
            self.status = self.STATUS_EXPIRED
            self.save(update_fields=["status"])


class RechargeTransaction(models.Model):
    """Every recharge/top-up event, whether via portal, app, or reseller."""

    CHANNEL_PORTAL = "portal"
    CHANNEL_APP = "app"
    CHANNEL_RESELLER = "reseller"
    CHANNEL_ROUTER_CAPTIVE = "router_captive_portal"
    CHANNEL_CHOICES = [
        (CHANNEL_PORTAL, "Web Portal"),
        (CHANNEL_APP, "Mobile App"),
        (CHANNEL_RESELLER, "Reseller"),
        (CHANNEL_ROUTER_CAPTIVE, "Router Captive Portal"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    chip = models.ForeignKey(IdentityChip, on_delete=models.CASCADE, related_name="recharges")
    plan = models.ForeignKey(Plan, on_delete=models.SET_NULL, null=True, blank=True)
    amount = models.DecimalField(max_digits=8, decimal_places=2)
    channel = models.CharField(max_length=32, choices=CHANNEL_CHOICES)
    reference = models.CharField(max_length=100, blank=True, help_text="Gateway/reseller transaction ref.")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.chip_id} +{self.amount} via {self.channel}"


class DailyUsageSummary(models.Model):
    """Rolled-up daily usage per chip, written by a Celery beat job — cheap
    to query for dashboards without scanning raw AAASession rows."""

    chip = models.ForeignKey(IdentityChip, on_delete=models.CASCADE, related_name="daily_usage")
    date = models.DateField()
    bytes_uploaded = models.BigIntegerField(default=0)
    bytes_downloaded = models.BigIntegerField(default=0)
    session_count = models.PositiveIntegerField(default=0)

    class Meta:
        unique_together = ("chip", "date")
        ordering = ["-date"]

    def __str__(self):
        return f"{self.chip_id} {self.date}"
