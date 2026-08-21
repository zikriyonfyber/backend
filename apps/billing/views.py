"""
apps.billing.views

NOTE on payments: this module records recharges and activates plans; it
intentionally does not embed a specific payment gateway SDK (JazzCash,
Easypaisa, bank rails, etc. vary by deployment region). Wire your
gateway's webhook to call `RechargeConfirmView` after the gateway
confirms payment, passing `payment_reference`.
"""
from django.db import transaction
from django.utils import timezone
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Plan, RechargeTransaction, Subscription
from .serializers import (
    PlanSerializer,
    RechargeRequestSerializer,
    RechargeTransactionSerializer,
    SubscriptionSerializer,
)


class PlanListView(generics.ListAPIView):
    queryset = Plan.objects.filter(is_active=True)
    serializer_class = PlanSerializer
    permission_classes = [permissions.AllowAny]


class CurrentSubscriptionView(generics.RetrieveAPIView):
    serializer_class = SubscriptionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        chip = self.request.user.chip
        return (
            Subscription.objects.filter(chip=chip).order_by("-started_at").first()
        )

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance is None:
            return Response({"detail": "No subscription yet."}, status=status.HTTP_404_NOT_FOUND)
        return Response(self.get_serializer(instance).data)


class RechargeHistoryView(generics.ListAPIView):
    serializer_class = RechargeTransactionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return RechargeTransaction.objects.filter(chip=self.request.user.chip)


class RechargeConfirmView(APIView):
    """
    Called once a payment (portal, app, reseller, or router captive
    portal top-up) is confirmed. Records the transaction, credits the
    chip balance, and activates/renews the Subscription.
    """
    permission_classes = [permissions.IsAuthenticated]

    @transaction.atomic
    def post(self, request):
        serializer = RechargeRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        plan = Plan.objects.select_for_update().get(
            slug=serializer.validated_data["plan_slug"], is_active=True
        )
        chip = request.user.chip

        RechargeTransaction.objects.create(
            chip=chip,
            plan=plan,
            amount=plan.price,
            channel=RechargeTransaction.CHANNEL_PORTAL,
            reference=serializer.validated_data.get("payment_reference", ""),
        )

        # Supersede any currently-active subscription with the new one.
        Subscription.objects.filter(chip=chip, status=Subscription.STATUS_ACTIVE).update(
            status=Subscription.STATUS_EXPIRED
        )
        subscription = Subscription.objects.create(chip=chip, plan=plan)

        return Response(
            SubscriptionSerializer(subscription).data, status=status.HTTP_201_CREATED
        )
