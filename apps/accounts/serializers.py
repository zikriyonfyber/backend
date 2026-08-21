from rest_framework import serializers
from rest_framework_simplejwt.tokens import RefreshToken

from .models import IdentityChip, Subscriber


class SubscriberRegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)

    class Meta:
        model = Subscriber
        fields = ["phone_number", "full_name", "email", "address", "password"]

    def create(self, validated_data):
        password = validated_data.pop("password")
        return Subscriber.objects.create_user(password=password, **validated_data)


class ChipLoginSerializer(serializers.Serializer):
    """
    Login for the recharge portal / mobile app using the chip ID printed
    on the Zikriyon Fyber card, plus the subscriber's account password.
    """
    chip_id = serializers.CharField(max_length=32)
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        try:
            chip = IdentityChip.objects.select_related("subscriber").get(
                chip_id=attrs["chip_id"]
            )
        except IdentityChip.DoesNotExist:
            raise serializers.ValidationError("Invalid chip ID or password.")

        if not chip.subscriber or not chip.subscriber.check_password(attrs["password"]):
            raise serializers.ValidationError("Invalid chip ID or password.")

        if chip.status != IdentityChip.STATUS_ACTIVE:
            raise serializers.ValidationError(f"Chip is {chip.status}; contact ZEAIPC support.")

        attrs["subscriber"] = chip.subscriber
        attrs["chip"] = chip
        return attrs

    def tokens(self):
        refresh = RefreshToken.for_user(self.validated_data["subscriber"])
        return {"refresh": str(refresh), "access": str(refresh.access_token)}


class IdentityChipSerializer(serializers.ModelSerializer):
    class Meta:
        model = IdentityChip
        fields = ["chip_id", "status", "balance", "issued_at", "last_seen_at"]
        read_only_fields = fields


class SubscriberProfileSerializer(serializers.ModelSerializer):
    chip = IdentityChipSerializer(read_only=True)

    class Meta:
        model = Subscriber
        fields = ["id", "phone_number", "full_name", "email", "address", "date_joined", "chip"]
        read_only_fields = ["id", "phone_number", "date_joined"]
