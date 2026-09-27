from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    AssignStudentFeeView,
    CancelStudentFeeView,
    FeeHeadViewSet,
    FeeStructureViewSet,
    OutstandingReportView,
    PaymentReceiptView,
    RecordPaymentView,
    ReversePaymentView,
    StudentFeesView,
    StudentFeeUpdateView,
    StudentPaymentsView,
)

router = DefaultRouter()
router.register(r"heads", FeeHeadViewSet, basename="fee-head")
router.register(r"structures", FeeStructureViewSet, basename="fee-structure")

urlpatterns = [
    path("students/<uuid:student_id>/", StudentFeesView.as_view(), name="student-fees"),
    path("students/<uuid:student_id>/assign/", AssignStudentFeeView.as_view(), name="student-fee-assign"),
    path("students/<uuid:student_id>/fees/<uuid:fee_id>/", StudentFeeUpdateView.as_view(), name="student-fee-update"),
    path("students/<uuid:student_id>/cancel/<uuid:fee_id>/", CancelStudentFeeView.as_view(), name="student-fee-cancel"),
    path("students/<uuid:student_id>/payments/", StudentPaymentsView.as_view(), name="student-payments"),
    path("payments/", RecordPaymentView.as_view(), name="record-payment"),
    path("payments/<uuid:payment_id>/receipt/", PaymentReceiptView.as_view(), name="payment-receipt"),
    path("payments/<uuid:payment_id>/reverse/", ReversePaymentView.as_view(), name="payment-reverse"),
    path("reports/outstanding/", OutstandingReportView.as_view(), name="outstanding-report"),
    path("", include(router.urls)),
]
