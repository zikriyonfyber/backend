from rest_framework import generics, permissions, status
from rest_framework.permissions import BasePermission
from rest_framework.response import Response
from rest_framework.views import APIView

from .auth import SIPServerAuthentication, SIPServerPrincipal
from .models import CallRecord, SIPNumber
from .serializers import (
    CallRecordSerializer,
    CDRWebhookSerializer,
    RouteDecisionRequestSerializer,
    SIPNumberSerializer,
)
from .services import authorize_call


class IsSIPServer(BasePermission):
    def has_permission(self, request, view):
        return isinstance(request.user, SIPServerPrincipal)


class SIPServerOnlyAPIView(APIView):
    authentication_classes = [SIPServerAuthentication]
    permission_classes = [IsSIPServer]


class RouteDecisionView(SIPServerOnlyAPIView):
    """
    Kamailio calls this (via its `exec`/REST-client module) before
    forwarding an INVITE, to decide: forward on-network for free,
    forward with PSTN billing, or reject.
    """

    def post(self, request):
        serializer = RouteDecisionRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        result = authorize_call(
            serializer.validated_data["caller_number"],
            serializer.validated_data["callee_number"],
        )
        return Response(
            {
                "allowed": result.allowed,
                "reason": result.reason,
                "billed": result.billed,
                "rate_per_minute": str(result.rate_per_minute),
            },
            status=status.HTTP_200_OK,
        )


class CDRWebhookView(SIPServerOnlyAPIView):
    """Receives the call-detail record once the SIP server tears down a call."""

    def post(self, request):
        serializer = CDRWebhookSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        caller = SIPNumber.objects.filter(number=data["caller_number"]).first()
        callee = SIPNumber.objects.filter(number=data["callee_number"]).first()

        billed_amount = 0
        if data["direction"] == CallRecord.DIRECTION_PSTN_OUT and caller:
            from decimal import Decimal
            minutes = max(1, -(-data["duration_seconds"] // 60))  # round up
            billed_amount = Decimal("2.00") * minutes
            caller.chip.balance = caller.chip.balance - billed_amount
            caller.chip.save(update_fields=["balance"])

        record, _ = CallRecord.objects.update_or_create(
            call_id=data["call_id"],
            defaults=dict(
                caller=caller,
                callee_number=data["callee_number"],
                callee=callee,
                direction=data["direction"],
                status=data["status"],
                started_at=data["started_at"],
                answered_at=data.get("answered_at"),
                ended_at=data.get("ended_at"),
                duration_seconds=data["duration_seconds"],
                billed_amount=billed_amount,
            ),
        )
        return Response(CallRecordSerializer(record).data, status=status.HTTP_201_CREATED)


class MySIPNumberView(generics.RetrieveAPIView):
    serializer_class = SIPNumberSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user.chip.sip_number


class MyCallHistoryView(generics.ListAPIView):
    serializer_class = CallRecordSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        sip_number = self.request.user.chip.sip_number
        return CallRecord.objects.filter(caller=sip_number) | CallRecord.objects.filter(callee=sip_number)
