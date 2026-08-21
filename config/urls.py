from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

admin.site.site_header = "ZEAIPC Network Operations"
admin.site.site_title = "ZEAIPC Admin"
admin.site.index_title = "Zikriyon Fyber Network Dashboard"

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/router/", include("apps.routerapi.urls")),
    path("api/accounts/", include("apps.accounts.urls")),
    path("api/billing/", include("apps.billing.urls")),
    path("api/voip/", include("apps.voip.urls")),
    path("api/weather/", include("apps.weather.urls")),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="docs"),
]
