"""
apps.routerapi.views — the endpoints Zikriyon Fyber router firmware calls.

Endpoints (all require X-Router-Serial / X-Router-Key headers):
    POST /api/router/chip-auth/       Authentication + Authorization
    POST /api/router/accounting/start/    Accounting: session open
    POST /api/router/accounting/interim/  Accounting: byte-counter update
    POST /api/router/accounting/stop/     Accounting: session close
    POST /api/router/heartbeat/           Router liveness + firmware/location
"""
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.accounts.models import AAASession, IdentityChip
from apps.billing.models import Subscription
from apps.voip.services import provision_sip_number_for_chip

from .auth import RouterAPIKeyAuthentication
from .permissions import IsAuthenticatedRouter
from .serializers import (
    AccountingInterimSerializer,
    AccountingStartSerializer,
    AccountingStopSerializer,
    ChipAuthRequestSerializer,
    HeartbeatSerializer,
)


class RouterOnlyAPIView(APIView):
    authentication_classes = [RouterAPIKeyAuthentication]
    permission_classes = [IsAuthenticated, IsAuthenticatedRouter]


class ChipAuthView(RouterOnlyAPIView):
    """
    Authentication + Authorization step. The router calls this whenever
    a chip is inserted / a client requests network access. Returns
    everything the captive portal needs to render, and everything the
    router needs to decide whether to grant data access.
    """
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "chip-auth"

    def post(self, request):
        serializer = ChipAuthRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        chip_id = serializer.validated_data["chip_id"]

        try:
            chip = IdentityChip.objects.select_related("subscriber").get(chip_id=chip_id)
        except IdentityChip.DoesNotExist:
            return Response(
                {"authenticated": False, "reason": "unknown_chip"},
                status=status.HTTP_404_NOT_FOUND,
            )

        router = request.user.router
        chip.last_seen_at = timezone.now()
        chip.last_seen_router = router
        chip.save(update_fields=["last_seen_at", "last_seen_router"])

        if not chip.is_authenticatable:
            return Response(
                {
                    "authenticated": False,
                    "reason": f"chip_status_{chip.status}",
                    "chip_id": chip.chip_id,
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        subscription = (
            Subscription.objects.filter(chip=chip).order_by("-started_at").first()
        )
        data_authorized = bool(subscription and subscription.is_currently_valid)

        # Offline-VoIP guarantee: SIP number is provisioned/ensured
        # regardless of data-plan status.
        sip_number, _ = provision_sip_number_for_chip(chip)

        return Response(
            {
                "authenticated": True,
                "data_authorized": data_authorized,
                "chip": {
                    "chip_id": chip.chip_id,
                    "status": chip.status,
                    "balance": str(chip.balance),
                    "subscriber_name": chip.subscriber.full_name,
                    "phone_number": chip.subscriber.phone_number,
                },
                "plan": (
                    {
                        "name": subscription.plan.name,
                        "expires_at": subscription.expires_at.isoformat(),
                        "data_cap_mb": subscription.plan.data_cap_mb,
                        "data_used_mb": str(subscription.data_used_mb),
                        "download_speed_mbps": subscription.plan.download_speed_mbps,
                        "upload_speed_mbps": subscription.plan.upload_speed_mbps,
                    }
                    if subscription
                    else None
                ),
                "voip": {
                    "sip_number": sip_number.number,
                    "sip_domain": sip_number.sip_uri.split("@")[1],
                    "sip_password": sip_number.sip_password,
                    "always_on": True,
                },
            },
            status=status.HTTP_200_OK,
        )


class AccountingStartView(RouterOnlyAPIView):
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "accounting"

    def post(self, request):
        serializer = AccountingStartSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        chip = IdentityChip.objects.filter(
            chip_id=serializer.validated_data["chip_id"]
        ).first()
        if not chip:
            return Response({"detail": "unknown_chip"}, status=status.HTTP_404_NOT_FOUND)

        # Close any stale open sessions for this chip on this router first.
        AAASession.objects.filter(
            chip=chip, router=request.user.router, status=AAASession.STATUS_OPEN
        ).update(status=AAASession.STATUS_CLOSED, stopped_at=timezone.now())

        session = AAASession.objects.create(
            chip=chip,
            router=request.user.router,
            client_ip=serializer.validated_data["client_ip"],
        )
        return Response({"session_id": str(session.id)}, status=status.HTTP_201_CREATED)


class AccountingInterimView(RouterOnlyAPIView):
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "accounting"

    def post(self, request):
        serializer = AccountingInterimSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        try:
            session = AAASession.objects.get(
                id=data["session_id"], router=request.user.router, status=AAASession.STATUS_OPEN
            )
        except AAASession.DoesNotExist:
            return Response({"detail": "unknown_or_closed_session"}, status=status.HTTP_404_NOT_FOUND)

        session.bytes_uploaded = data["bytes_uploaded"]
        session.bytes_downloaded = data["bytes_downloaded"]
        session.last_interim_at = timezone.now()
        session.save(update_fields=["bytes_uploaded", "bytes_downloaded", "last_interim_at"])

        subscription = Subscription.objects.filter(
            chip=session.chip, status=Subscription.STATUS_ACTIVE
        ).order_by("-started_at").first()
        if subscription:
            total_mb = (data["bytes_uploaded"] + data["bytes_downloaded"]) / (1024 * 1024)
            subscription.register_usage(total_mb)

        return Response({"detail": "ok"}, status=status.HTTP_200_OK)


class AccountingStopView(RouterOnlyAPIView):
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "accounting"

    def post(self, request):
        serializer = AccountingStopSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        try:
            session = AAASession.objects.get(id=data["session_id"], router=request.user.router)
        except AAASession.DoesNotExist:
            return Response({"detail": "unknown_session"}, status=status.HTTP_404_NOT_FOUND)

        session.bytes_uploaded = data["bytes_uploaded"]
        session.bytes_downloaded = data["bytes_downloaded"]
        session.close()
        return Response({"detail": "ok"}, status=status.HTTP_200_OK)


class HeartbeatView(RouterOnlyAPIView):
    def post(self, request):
        serializer = HeartbeatSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        router = request.user.router
        for field in ("firmware_version", "latitude", "longitude"):
            if field in serializer.validated_data:
                setattr(router, field, serializer.validated_data[field])
        router.last_heartbeat_at = timezone.now()
        router.save()
        return Response({"detail": "ok"}, status=status.HTTP_200_OK)
