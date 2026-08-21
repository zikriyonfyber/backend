from django.urls import path

from . import views

app_name = "billing"

urlpatterns = [
    path("plans/", views.PlanListView.as_view(), name="plan-list"),
    path("subscription/current/", views.CurrentSubscriptionView.as_view(), name="subscription-current"),
    path("recharge/", views.RechargeConfirmView.as_view(), name="recharge"),
    path("recharge/history/", views.RechargeHistoryView.as_view(), name="recharge-history"),
]
