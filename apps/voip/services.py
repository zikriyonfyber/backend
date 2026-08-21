"""
Services backing Zikriyon Fyber's "offline calling" guarantee:

    Two subscribers with active chips and routers can always call each
    other over the ISP's own network, even if neither has an active
    data plan or balance. Only PSTN breakout is gated by billing.

Kamailio is configured with a second DB connection (alias "kamailio" in
DATABASES, pointed at Kamailio's own schema) so this Django app remains
the single source of truth for SIP credentials; `sync_subscriber_to_kamailio`
mirrors a SIPNumber into Kamailio's `subscriber` table on every
create/update via the post_save signal in signals.py.
"""
from decimal import Decimal

from django.conf import settings
from django.db import connections
from django.utils import timezone

from apps.billing.models import Subscription
from apps.voip.models import SIPNumber

# Kamailio's default auth_db module schema (username, domain, ha1, ha1b).
_KAMAILIO_UPSERT_SQL = """
    INSERT INTO subscriber (username, domain, password, ha1, ha1b)
    VALUES (%(username)s, %(domain)s, %(password)s, %(ha1)s, %(ha1b)s)
    ON CONFLICT (username, domain) DO UPDATE
        SET password = EXCLUDED.password,
            ha1 = EXCLUDED.ha1,
            ha1b = EXCLUDED.ha1b
"""


def _ha1(username, domain, password):
    import hashlib
    return hashlib.md5(f"{username}:{domain}:{password}".encode()).hexdigest()


def sync_subscriber_to_kamailio(sip_number: SIPNumber):
    """Push (or refresh) this subscriber's SIP credentials into Kamailio's
    auth DB so the registrar/proxy can authenticate REGISTER/INVITE."""
    domain = settings.ZEAIPC["SIP_DOMAIN"]
    params = {
        "username": sip_number.number,
        "domain": domain,
        "password": sip_number.sip_password,
        "ha1": _ha1(sip_number.number, domain, sip_number.sip_password),
        "ha1b": _ha1(f"{sip_number.number}@{domain}", domain, sip_number.sip_password),
    }
    with connections["kamailio"].cursor() as cursor:
        cursor.execute(_KAMAILIO_UPSERT_SQL, params)


def deactivate_subscriber_in_kamailio(sip_number: SIPNumber):
    domain = settings.ZEAIPC["SIP_DOMAIN"]
    with connections["kamailio"].cursor() as cursor:
        cursor.execute(
            "DELETE FROM subscriber WHERE username = %s AND domain = %s",
            [sip_number.number, domain],
        )


class CallAuthorizationResult:
    def __init__(self, allowed: bool, reason: str, billed: bool = False, rate: Decimal = Decimal("0")):
        self.allowed = allowed
        self.reason = reason
        self.billed = billed
        self.rate_per_minute = rate


def authorize_call(caller_number: str, callee_number: str) -> CallAuthorizationResult:
    """
    Called by Kamailio via its REST/JSON-RPC route-decision hook
    (see apps.voip.views.RouteDecisionView) before it forwards an INVITE.

    On-network calls: always allowed, ignoring balance/subscription.
    PSTN breakout: requires the caller's chip to have pstn_breakout_enabled
    and either a valid data subscription or sufficient prepaid balance.
    """
    try:
        caller = SIPNumber.objects.select_related("chip").get(number=caller_number, is_active=True)
    except SIPNumber.DoesNotExist:
        return CallAuthorizationResult(False, "Caller has no active Zikriyon Fyber SIP line.")

    if caller.chip.status != caller.chip.STATUS_ACTIVE:
        return CallAuthorizationResult(False, "Caller's identity chip is not active.")

    on_network = SIPNumber.objects.filter(number=callee_number, is_active=True).exists()
    prefix = settings.ZEAIPC["SIP_NUMBER_PREFIX"]

    if on_network or callee_number.startswith(prefix):
        # Core guarantee: never gated by billing status.
        if settings.ZEAIPC["OFFLINE_VOIP_ALWAYS_ON"]:
            return CallAuthorizationResult(True, "On-network call — free, always permitted.")

    # PSTN breakout path — billed, requires balance.
    if not caller.pstn_breakout_enabled:
        return CallAuthorizationResult(False, "PSTN breakout not enabled for this chip.")

    rate = Decimal("2.00")  # currency units per minute; move to a RatePlan model as this scales
    if caller.chip.balance < rate:
        return CallAuthorizationResult(False, "Insufficient balance for PSTN call.")

    return CallAuthorizationResult(True, "PSTN call authorized.", billed=True, rate=rate)


def provision_sip_number_for_chip(chip):
    """Idempotently ensure an active chip has a SIP number, and sync it
    to Kamailio. Called from the accounts signal on chip activation and
    from the router chip-auth flow as a safety net."""
    sip_number, created = SIPNumber.objects.get_or_create(chip=chip)
    sync_subscriber_to_kamailio(sip_number)
    return sip_number, created
