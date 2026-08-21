from django.urls import path

from . import views

app_name = "voip"

urlpatterns = [
    path("sip-server/route-decision/", views.RouteDecisionView.as_view(), name="route-decision"),
    path("sip-server/cdr/", views.CDRWebhookView.as_view(), name="cdr-webhook"),
    path("me/number/", views.MySIPNumberView.as_view(), name="my-number"),
    path("me/calls/", views.MyCallHistoryView.as_view(), name="my-calls"),
]
