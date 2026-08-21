from rest_framework import serializers

from .models import WeatherLocation, WeatherReading


class WeatherReadingSerializer(serializers.ModelSerializer):
    location_name = serializers.CharField(source="location.name", read_only=True)

    class Meta:
        model = WeatherReading
        fields = [
            "location_name", "temperature_c", "feels_like_c", "humidity_percent",
            "wind_speed_kph", "condition", "icon_code", "observed_at",
        ]
        read_only_fields = fields
