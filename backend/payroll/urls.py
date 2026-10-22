from django.urls import include, path
from rest_framework.routers import SimpleRouter

from .views import PayrollSettingsView, SalaryComponentViewSet, StaffSalaryComponentViewSet, StaffSalaryViewSet

router = SimpleRouter()
router.register(r"components", SalaryComponentViewSet, basename="payroll-component")
router.register(r"salaries", StaffSalaryViewSet, basename="payroll-salary")
router.register(r"staff-components", StaffSalaryComponentViewSet, basename="payroll-staff-component")

urlpatterns = [
    path("settings/", PayrollSettingsView.as_view(), name="payroll-settings"),
    path("", include(router.urls)),
]
