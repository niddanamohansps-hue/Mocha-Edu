from django.contrib import admin
from django.urls import include, path

from .health import health

urlpatterns = [
    path("api/health/", health, name="health"),
    path("admin/", admin.site.urls),
    path("api/auth/", include("accounts.urls")),
    path("api/payments/", include("payments.urls")),
    path("api/organizations/", include("organizations.urls")),
    path("api/billing/", include("billing.urls")),
]

