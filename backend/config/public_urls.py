from django.contrib import admin
from django.urls import include, path

from .health import health
from billing.admin_dashboard import billing_dashboard

urlpatterns = [
    # Before "admin/" so the admin does not treat it as a model URL.
    path("admin/billing/dashboard/", billing_dashboard, name="billing-dashboard"),
    path("api/health/", health, name="health"),
    path("admin/", admin.site.urls),
    path("api/auth/", include("accounts.urls")),
    path("api/payments/", include("payments.urls")),
    path("api/organizations/", include("organizations.urls")),
    path("api/billing/", include("billing.urls")),
]

