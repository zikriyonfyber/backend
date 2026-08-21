from django.contrib import admin

from .models import WeatherLocation, WeatherReading


@admin.register(WeatherLocation)
class WeatherLocationAdmin(admin.ModelAdmin):
    list_display = ["name", "latitude", "longitude"]
    search_fields = ["name"]


@admin.register(WeatherReading)
class WeatherReadingAdmin(admin.ModelAdmin):
    list_display = ["location", "temperature_c", "condition", "observed_at"]
    list_filter = ["location"]
    date_hierarchy = "observed_at"
