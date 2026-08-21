from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    path("register/", views.RegisterView.as_view(), name="register"),
    path("login/", views.ChipLoginView.as_view(), name="chip-login"),
    path("me/", views.ProfileView.as_view(), name="profile"),
]
