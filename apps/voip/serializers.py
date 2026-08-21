from rest_framework import serializers

from .models import CallRecord, SIPNumber


class SIPNumberSerializer(serializers.ModelSerializer):
    class Meta:
        model = SIPNumber
        fields = ["number", "is_active", "pstn_breakout_enabled", "created_at"]
        read_only_fields = fields


class CallRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = CallRecord
        fields = [
            "id", "call_id", "callee_number", "direction", "status",
            "started_at", "answered_at", "ended_at", "duration_seconds",
            "billed_amount",
        ]
        read_only_fields = fields


class RouteDecisionRequestSerializer(serializers.Serializer):
    """What Kamailio's route-decision hook sends before forwarding an INVITE."""
    caller_number = serializers.CharField(max_length=32)
    callee_number = serializers.CharField(max_length=32)


class CDRWebhookSerializer(serializers.Serializer):
    """What Kamailio/FreeSWITCH's accounting module posts at call teardown."""
    call_id = serializers.CharField(max_length=255)
    caller_number = serializers.CharField(max_length=32)
    callee_number = serializers.CharField(max_length=32)
    direction = serializers.ChoiceField(choices=CallRecord.DIRECTION_CHOICES)
    status = serializers.ChoiceField(choices=CallRecord.STATUS_CHOICES)
    started_at = serializers.DateTimeField()
    answered_at = serializers.DateTimeField(required=False, allow_null=True)
    ended_at = serializers.DateTimeField(required=False, allow_null=True)
    duration_seconds = serializers.IntegerField(min_value=0, default=0)
