from django.urls import path

from . import views

app_name = "routerapi"

urlpatterns = [
    path("chip-auth/", views.ChipAuthView.as_view(), name="chip-auth"),
    path("accounting/start/", views.AccountingStartView.as_view(), name="accounting-start"),
    path("accounting/interim/", views.AccountingInterimView.as_view(), name="accounting-interim"),
    path("accounting/stop/", views.AccountingStopView.as_view(), name="accounting-stop"),
    path("heartbeat/", views.HeartbeatView.as_view(), name="heartbeat"),
]
