from django.urls import path

from . import views

app_name = "weather"

urlpatterns = [
    path("latest/", views.LatestWeatherView.as_view(), name="latest"),
]
