"""
Router-facing authentication.

Routers (Zikriyon Fyber CPEs) never log in as a Django user — they carry
a per-device serial number + API key issued at provisioning time. This
class authenticates the *router* as a principal so router-only endpoints
(chip auth, accounting, heartbeat) can require it via DRF permissions,
independently of subscriber JWT auth used by the recharge portal/app.

Router sends:
    X-Router-Serial: <serial_number>
    X-Router-Key: <raw api key issued at provisioning>
"""
from rest_framework import authentication, exceptions

from apps.accounts.models import RouterDevice


class RouterPrincipal:
    """Duck-typed stand-in for a Django user, scoped to a RouterDevice."""

    is_authenticated = True
    is_anonymous = False

    def __init__(self, router: RouterDevice):
        self.router = router
        self.id = router.pk
        self.is_staff = False
        self.is_superuser = False

    def __str__(self):
        return f"router:{self.router.serial_number}"


class RouterAPIKeyAuthentication(authentication.BaseAuthentication):
    def authenticate(self, request):
        serial = request.headers.get("X-Router-Serial")
        raw_key = request.headers.get("X-Router-Key")
        if not serial or not raw_key:
            return None  # let other authenticators (JWT) try

        try:
            router = RouterDevice.objects.get(serial_number=serial, is_active=True)
        except RouterDevice.DoesNotExist:
            raise exceptions.AuthenticationFailed("Unknown or disabled router.")

        if not router.check_api_key(raw_key):
            raise exceptions.AuthenticationFailed("Invalid router API key.")

        return (RouterPrincipal(router), None)

    def authenticate_header(self, request):
        return "X-Router-Key"
