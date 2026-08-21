"""
apps.weather — polls an upstream weather provider for every distinct
router install location and serves cached readings to routers (for the
captive portal) and the Next.js dashboard. Routers never call the
upstream provider directly; they only ever talk to this Django API,
which keeps provider API keys server-side and lets thousands of routers
share one set of cached readings per region instead of hammering the
upstream provider.
"""
from django.db import models


class WeatherLocation(models.Model):
    name = models.CharField(max_length=120)
    latitude = models.FloatField()
    longitude = models.FloatField()

    class Meta:
        unique_together = ("latitude", "longitude")

    def __str__(self):
        return f"{self.name} ({self.latitude}, {self.longitude})"


class WeatherReading(models.Model):
    location = models.ForeignKey(WeatherLocation, on_delete=models.CASCADE, related_name="readings")
    temperature_c = models.FloatField()
    feels_like_c = models.FloatField(null=True, blank=True)
    humidity_percent = models.FloatField(null=True, blank=True)
    wind_speed_kph = models.FloatField(null=True, blank=True)
    condition = models.CharField(max_length=100, blank=True)
    icon_code = models.CharField(max_length=20, blank=True)
    observed_at = models.DateTimeField()
    fetched_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-observed_at"]
        indexes = [models.Index(fields=["location", "-observed_at"])]

    def __str__(self):
        return f"{self.location.name} @ {self.observed_at}: {self.temperature_c}C"
