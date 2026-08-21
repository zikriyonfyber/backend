"""
Authenticates callbacks coming FROM the SIP server (Kamailio's htable/
exec module route-decision hook, FreeSWITCH's mod_xml_curl / mod_cdr_pg
webhook) — not from a router or a subscriber. Uses a shared secret
configured identically on both sides (Kamailio's `htable` config /
FreeSWITCH's curl module headers and settings.ZEAIPC.SIP_SERVER_SECRET).
"""
import hmac

from django.conf import settings
from rest_framework import authentication, exceptions


class SIPServerPrincipal:
    is_authenticated = True
    is_anonymous = False

    def __str__(self):
        return "sip-server"


class SIPServerAuthentication(authentication.BaseAuthentication):
    def authenticate(self, request):
        provided = request.headers.get("X-SIP-Server-Secret")
        if not provided:
            return None
        expected = settings.ZEAIPC.get("SIP_SERVER_SECRET", "")
        if not expected or not hmac.compare_digest(provided, expected):
            raise exceptions.AuthenticationFailed("Invalid SIP server secret.")
        return (SIPServerPrincipal(), None)

    def authenticate_header(self, request):
        return "X-SIP-Server-Secret"
