from rest_framework import serializers


class ChipAuthRequestSerializer(serializers.Serializer):
    chip_id = serializers.CharField(max_length=32)
    client_mac = serializers.CharField(max_length=17, required=False, allow_blank=True)


class AccountingStartSerializer(serializers.Serializer):
    chip_id = serializers.CharField(max_length=32)
    client_ip = serializers.IPAddressField()


class AccountingInterimSerializer(serializers.Serializer):
    session_id = serializers.UUIDField()
    bytes_uploaded = serializers.IntegerField(min_value=0)
    bytes_downloaded = serializers.IntegerField(min_value=0)


class AccountingStopSerializer(serializers.Serializer):
    session_id = serializers.UUIDField()
    bytes_uploaded = serializers.IntegerField(min_value=0)
    bytes_downloaded = serializers.IntegerField(min_value=0)


class HeartbeatSerializer(serializers.Serializer):
    firmware_version = serializers.CharField(max_length=32, required=False, allow_blank=True)
    latitude = serializers.FloatField(required=False)
    longitude = serializers.FloatField(required=False)
