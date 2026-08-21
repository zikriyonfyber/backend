"""
Weather provider integration. Written against the OpenWeatherMap
"Current Weather" API shape — swap `_call_provider` if your deployment
uses a different provider; everything downstream (models, API, router
firmware) is provider-agnostic.
"""
import logging

import requests
from django.conf import settings
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from .models import WeatherLocation, WeatherReading

logger = logging.getLogger("zeaipc.weather")

PROVIDER_URL = "https://api.openweathermap.org/data/2.5/weather"


def _call_provider(lat: float, lon: float) -> dict:
    api_key = settings.ZEAIPC["WEATHER_PROVIDER_API_KEY"]
    response = requests.get(
        PROVIDER_URL,
        params={"lat": lat, "lon": lon, "appid": api_key, "units": "metric"},
        timeout=10,
    )
    response.raise_for_status()
    return response.json()


def fetch_and_store_reading(location: WeatherLocation) -> WeatherReading:
    payload = _call_provider(location.latitude, location.longitude)
    weather = (payload.get("weather") or [{}])[0]
    main = payload.get("main", {})
    wind = payload.get("wind", {})

    reading = WeatherReading.objects.create(
        location=location,
        temperature_c=main.get("temp"),
        feels_like_c=main.get("feels_like"),
        humidity_percent=main.get("humidity"),
        wind_speed_kph=(wind.get("speed") or 0) * 3.6,
        condition=weather.get("description", ""),
        icon_code=weather.get("icon", ""),
        observed_at=timezone.now(),
    )
    return reading


def sync_locations_from_active_routers():
    """Ensure every router install location has a WeatherLocation to poll."""
    from apps.accounts.models import RouterDevice

    routers = RouterDevice.objects.filter(
        is_active=True, latitude__isnull=False, longitude__isnull=False
    )
    for router in routers:
        WeatherLocation.objects.get_or_create(
            latitude=round(router.latitude, 2),
            longitude=round(router.longitude, 2),
            defaults={"name": router.install_location or router.serial_number},
        )


def poll_all_locations():
    sync_locations_from_active_routers()
    for location in WeatherLocation.objects.all():
        try:
            fetch_and_store_reading(location)
        except requests.RequestException:
            logger.exception("Weather fetch failed for %s", location)
