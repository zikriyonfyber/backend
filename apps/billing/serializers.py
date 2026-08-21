from rest_framework import serializers

from .models import Plan, RechargeTransaction, Subscription


class PlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = Plan
        fields = [
            "id", "name", "slug", "description", "price", "cycle",
            "data_cap_mb", "download_speed_mbps", "upload_speed_mbps",
            "is_subsidized",
        ]


class SubscriptionSerializer(serializers.ModelSerializer):
    plan = PlanSerializer(read_only=True)

    class Meta:
        model = Subscription
        fields = ["id", "plan", "status", "started_at", "expires_at", "data_used_mb"]
        read_only_fields = fields


class RechargeRequestSerializer(serializers.Serializer):
    """Subscriber-initiated recharge from the portal/app."""
    plan_slug = serializers.SlugField()
    payment_reference = serializers.CharField(max_length=100, required=False, allow_blank=True)

    def validate_plan_slug(self, value):
        if not Plan.objects.filter(slug=value, is_active=True).exists():
            raise serializers.ValidationError("Unknown or inactive plan.")
        return value


class RechargeTransactionSerializer(serializers.ModelSerializer):
    plan = PlanSerializer(read_only=True)

    class Meta:
        model = RechargeTransaction
        fields = ["id", "plan", "amount", "channel", "reference", "created_at"]
        read_only_fields = fields
