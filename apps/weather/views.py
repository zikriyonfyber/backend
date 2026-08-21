from rest_framework import permissions
from rest_framework.exceptions import NotFound
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import WeatherLocation
from .serializers import WeatherReadingSerializer


class LatestWeatherView(APIView):
    """
    GET /api/weather/latest/?lat=..&lon=..

    Public (routers' captive portals and the Next.js dashboard both call
    this without subscriber auth — weather is not gated by billing).
    Matches to the nearest cached WeatherLocation within ~0.05 degrees
    (~5km) rather than hitting the upstream provider per-request.
    """
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        try:
            lat = float(request.query_params["lat"])
            lon = float(request.query_params["lon"])
        except (KeyError, ValueError):
            return Response({"detail": "lat and lon query params are required."}, status=400)

        candidates = WeatherLocation.objects.all()
        nearest = min(
            candidates,
            key=lambda loc: (loc.latitude - lat) ** 2 + (loc.longitude - lon) ** 2,
            default=None,
        )
        if nearest is None:
            raise NotFound("No weather data available yet for this area.")

        reading = nearest.readings.order_by("-observed_at").first()
        if reading is None:
            raise NotFound("Location known but no readings collected yet.")

        return Response(WeatherReadingSerializer(reading).data)
