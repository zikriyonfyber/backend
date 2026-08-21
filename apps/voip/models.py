"""
apps.voip — SIP number assignment + call detail records for Zikriyon
Fyber's offline (on-network) VoIP calling.

Design: every ACTIVE IdentityChip gets exactly one SIPNumber. Kamailio
(SIP proxy/registrar) is configured to authenticate against these
credentials via the `KamailioSubscriberSync` service in services.py,
which mirrors this table into Kamailio's own `subscriber`/`location`
schema. Call routing between two Zikriyon Fyber numbers never touches
billing/Subscription status — that's the "offline calling" guarantee:
users can always call each other on-network even with zero balance.
Only calls that break out to the PSTN (via a SIP trunk) are billed.
"""
import secrets
import uuid

from django.conf import settings
from django.db import models

from apps.accounts.models import IdentityChip


def _next_local_number():
    """Sequential local-number allocator scoped by the configured prefix."""
    prefix = settings.ZEAIPC["SIP_NUMBER_PREFIX"]
    last = (
        SIPNumber.objects.filter(number__startswith=prefix)
        .order_by("-number")
        .values_list("number", flat=True)
        .first()
    )
    next_seq = int(last[len(prefix):]) + 1 if last else 1
    return f"{prefix}{next_seq:06d}"


class SIPNumber(models.Model):
    """A Zikriyon Fyber on-network phone number bound to one identity chip."""

    number = models.CharField(max_length=20, primary_key=True, default=_next_local_number, editable=False)
    chip = models.OneToOneField(IdentityChip, on_delete=models.CASCADE, related_name="sip_number")
    sip_password = models.CharField(max_length=64, editable=False)
    is_active = models.BooleanField(default=True)
    pstn_breakout_enabled = models.BooleanField(
        default=False, help_text="Allow calls out to real phone numbers (billed, requires balance)."
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "SIP Number"
        verbose_name_plural = "SIP Numbers"

    def __str__(self):
        return f"{self.number} ({self.chip_id})"

    def save(self, *args, **kwargs):
        if not self.sip_password:
            self.sip_password = secrets.token_urlsafe(12)
        super().save(*args, **kwargs)

    @property
    def sip_uri(self):
        return f"sip:{self.number}@{settings.ZEAIPC['SIP_DOMAIN']}"


class CallRecord(models.Model):
    """CDR — one row per call, populated by Kamailio/FreeSWITCH's
    accounting callback (see apps.voip.views.CDRWebhookView)."""

    DIRECTION_ON_NET = "on_network"
    DIRECTION_PSTN_OUT = "pstn_outbound"
    DIRECTION_PSTN_IN = "pstn_inbound"
    DIRECTION_CHOICES = [
        (DIRECTION_ON_NET, "On-network (free)"),
        (DIRECTION_PSTN_OUT, "PSTN outbound (billed)"),
        (DIRECTION_PSTN_IN, "PSTN inbound"),
    ]

    STATUS_COMPLETED = "completed"
    STATUS_NO_ANSWER = "no_answer"
    STATUS_BUSY = "busy"
    STATUS_FAILED = "failed"
    STATUS_CHOICES = [
        (STATUS_COMPLETED, "Completed"),
        (STATUS_NO_ANSWER, "No Answer"),
        (STATUS_BUSY, "Busy"),
        (STATUS_FAILED, "Failed"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    call_id = models.CharField(max_length=255, unique=True, help_text="SIP Call-ID header, from Kamailio/FreeSWITCH.")
    caller = models.ForeignKey(
        SIPNumber, on_delete=models.SET_NULL, null=True, related_name="outgoing_calls"
    )
    callee_number = models.CharField(max_length=32)
    callee = models.ForeignKey(
        SIPNumber, on_delete=models.SET_NULL, null=True, blank=True, related_name="incoming_calls"
    )
    direction = models.CharField(max_length=16, choices=DIRECTION_CHOICES)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES)
    started_at = models.DateTimeField()
    answered_at = models.DateTimeField(null=True, blank=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    duration_seconds = models.PositiveIntegerField(default=0)
    billed_amount = models.DecimalField(max_digits=8, decimal_places=2, default=0)

    class Meta:
        ordering = ["-started_at"]
        indexes = [
            models.Index(fields=["caller", "started_at"]),
            models.Index(fields=["direction"]),
        ]

    def __str__(self):
        return f"{self.caller_id} -> {self.callee_number} ({self.status})"
