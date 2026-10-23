from django.urls import include, path
from rest_framework.routers import SimpleRouter

from .my_views import MyPayslipViewSet
from .run_views import PayrollAdjustmentViewSet, PayrollRunViewSet, PayslipViewSet
from .views import PayrollSettingsView, SalaryComponentViewSet, StaffSalaryComponentViewSet, StaffSalaryViewSet

router = SimpleRouter()
router.register(r"components", SalaryComponentViewSet, basename="payroll-component")
router.register(r"salaries", StaffSalaryViewSet, basename="payroll-salary")
router.register(r"staff-components", StaffSalaryComponentViewSet, basename="payroll-staff-component")
router.register(r"runs", PayrollRunViewSet, basename="payroll-run")
router.register(r"payslips", PayslipViewSet, basename="payroll-payslip")
router.register(r"my-payslips", MyPayslipViewSet, basename="payroll-my-payslip")
router.register(r"adjustments", PayrollAdjustmentViewSet, basename="payroll-adjustment")

urlpatterns = [
    path("settings/", PayrollSettingsView.as_view(), name="payroll-settings"),
    path("", include(router.urls)),
]
