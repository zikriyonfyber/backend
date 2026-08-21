"""
apps.accounts — AAA identity layer for ZEAIPC / Zikriyon Fyber.

Core idea: the physical router (Zikriyon Fyber CPE) is universal, dumb
hardware. All per-user state — profile, balance, VoIP number, plan — lives
on the IdentityChip. A router authenticates a *chip*, not a person; the
chip is what's swapped/reissued when a user's details change.

AAA mapping:
  Authentication -> ChipAuthView (router presents chip_id + router API key)
  Authorization  -> Subscriber.is_active / IdentityChip.status / plan checks
  Accounting     -> AAASession (open on connect, closed on disconnect, byte counters)
"""
import secrets
import uuid

from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.contrib.auth.models import PermissionsMixin
from django.db import models
from django.utils import timezone


class SubscriberManager(BaseUserManager):
    def create_user(self, phone_number, full_name, password=None, **extra_fields):
        if not phone_number:
            raise ValueError("Subscribers must have a phone number.")
        user = self.model(
            phone_number=phone_number,
            full_name=full_name,
            **extra_fields,
        )
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save(using=self._db)
        return user

    def create_superuser(self, phone_number, full_name, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)
        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")
        return self.create_user(phone_number, full_name, password, **extra_fields)


class Subscriber(AbstractBaseUser, PermissionsMixin):
    """A ZEAIPC subscriber. Identity/admin console login (portal, staff)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    phone_number = models.CharField(max_length=20, unique=True, db_index=True)
    full_name = models.CharField(max_length=150)
    email = models.EmailField(blank=True, null=True)
    address = models.CharField(max_length=255, blank=True)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(default=timezone.now)

    objects = SubscriberManager()

    USERNAME_FIELD = "phone_number"
    REQUIRED_FIELDS = ["full_name"]

    class Meta:
        verbose_name = "Subscriber"
        verbose_name_plural = "Subscribers"

    def __str__(self):
        return f"{self.full_name} ({self.phone_number})"


def generate_chip_id():
    """20-char alphanumeric ID etched/flashed onto the physical chip."""
    return "ZF-" + secrets.token_hex(8).upper()


class IdentityChip(models.Model):
    """
    The smart card / chip issued to a subscriber. This — not the router —
    is the unit of identity. Router hardware never changes per-user.
    """

    STATUS_ACTIVE = "active"
    STATUS_BLOCKED = "blocked"
    STATUS_LOST = "lost"
    STATUS_UNASSIGNED = "unassigned"
    STATUS_CHOICES = [
        (STATUS_ACTIVE, "Active"),
        (STATUS_BLOCKED, "Blocked"),
        (STATUS_LOST, "Reported Lost"),
        (STATUS_UNASSIGNED, "Unassigned (stock)"),
    ]

    chip_id = models.CharField(
        max_length=32, primary_key=True, default=generate_chip_id, editable=False
    )
    subscriber = models.OneToOneField(
        Subscriber, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="chip",
    )
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=STATUS_UNASSIGNED)

    # Balance is authoritative in the DB; the chip itself only *caches* the
    # last-synced balance for offline display on the router's captive portal.
    balance = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    cached_balance_synced_at = models.DateTimeField(null=True, blank=True)

    issued_at = models.DateTimeField(auto_now_add=True)
    last_seen_at = models.DateTimeField(null=True, blank=True)
    last_seen_router = models.ForeignKey(
        "accounts.RouterDevice", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="chips_last_seen",
    )

    class Meta:
        verbose_name = "Identity Chip"
        verbose_name_plural = "Identity Chips"
        indexes = [models.Index(fields=["status"])]

    def __str__(self):
        who = self.subscriber.full_name if self.subscriber else "unassigned"
        return f"{self.chip_id} ({who})"

    @property
    def is_authenticatable(self):
        return self.status == self.STATUS_ACTIVE and self.subscriber_id is not None


class RouterDevice(models.Model):
    """
    A physical Zikriyon Fyber CPE (ESP32-based router). Hardware is
    universal/interchangeable — identity lives on whichever chip is
    inserted, not on the router record.
    """

    serial_number = models.CharField(max_length=64, unique=True, db_index=True)
    mac_address = models.CharField(max_length=17, unique=True)
    api_key_hash = models.CharField(max_length=128, editable=False)
    firmware_version = models.CharField(max_length=32, blank=True)
    install_location = models.CharField(max_length=255, blank=True)
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    last_heartbeat_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Router (Zikriyon Fyber CPE)"
        verbose_name_plural = "Routers (Zikriyon Fyber CPE)"

    def __str__(self):
        return f"{self.serial_number} [{self.mac_address}]"

    def set_api_key(self, raw_key: str):
        from django.contrib.auth.hashers import make_password
        self.api_key_hash = make_password(raw_key)

    def check_api_key(self, raw_key: str) -> bool:
        from django.contrib.auth.hashers import check_password
        return check_password(raw_key, self.api_key_hash)

    @staticmethod
    def generate_api_key() -> str:
        return secrets.token_urlsafe(32)


class AAASession(models.Model):
    """
    Accounting record: one row per chip<->router connection session.
    Mirrors RADIUS accounting semantics (start / interim-update / stop)
    so this table can later be fed into a RADIUS-compatible reporting
    pipeline if the ISP scales into a full RADIUS deployment.
    """

    STATUS_OPEN = "open"
    STATUS_CLOSED = "closed"
    STATUS_CHOICES = [(STATUS_OPEN, "Open"), (STATUS_CLOSED, "Closed")]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    chip = models.ForeignKey(IdentityChip, on_delete=models.CASCADE, related_name="sessions")
    router = models.ForeignKey(RouterDevice, on_delete=models.CASCADE, related_name="sessions")
    status = models.CharField(max_length=8, choices=STATUS_CHOICES, default=STATUS_OPEN)

    client_ip = models.GenericIPAddressField(null=True, blank=True)
    bytes_uploaded = models.BigIntegerField(default=0)
    bytes_downloaded = models.BigIntegerField(default=0)

    started_at = models.DateTimeField(auto_now_add=True)
    last_interim_at = models.DateTimeField(null=True, blank=True)
    stopped_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "AAA Session"
        verbose_name_plural = "AAA Sessions"
        indexes = [
            models.Index(fields=["chip", "status"]),
            models.Index(fields=["router", "status"]),
        ]

    def close(self):
        self.status = self.STATUS_CLOSED
        self.stopped_at = timezone.now()
        self.save(update_fields=["status", "stopped_at"])

    @property
    def total_bytes(self):
        return self.bytes_uploaded + self.bytes_downloaded
