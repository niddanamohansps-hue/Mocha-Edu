from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .gateway_views import (
    GatewayDetailView,
    GatewayListView,
    GatewayTestView,
    PayableGatewaysView,
    RazorpayWebhookView,
)

from .views import (
    AssignStudentFeeView,
    CancelStudentFeeView,
    FeeHeadViewSet,
    FeeStructureViewSet,
    OnlinePaymentCallbackView,
    OnlinePaymentInitiateView,
    OnlinePaymentOrderDetailView,
    OnlinePaymentOrderListView,
    OnlinePaymentOrderReconcileView,
    OnlinePaymentVerifyView,
    DuesByStudentView,
    StudentCallsView,
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


from .paylink_views import PayLinkDetailView, PayLinkStartView

urlpatterns = [
    path("pay-link/<str:token>/", PayLinkDetailView.as_view(), name="fees-pay-link"),
    path("pay-link/<str:token>/start/", PayLinkStartView.as_view(), name="fees-pay-link-start"),
    path("gateways/", GatewayListView.as_view(), name="payment-gateway-list"),
    path("gateways/<str:gateway>/", GatewayDetailView.as_view(), name="payment-gateway-detail"),
    path("gateways/<str:gateway>/test/", GatewayTestView.as_view(), name="payment-gateway-test"),
    path("online/gateways/", PayableGatewaysView.as_view(), name="online-payment-gateways"),
    path("online/webhook/razorpay/", RazorpayWebhookView.as_view(), name="online-payment-webhook-razorpay"),
    path("online/initiate/", OnlinePaymentInitiateView.as_view(), name="online-payment-initiate"),
    path("online/verify/", OnlinePaymentVerifyView.as_view(), name="online-payment-verify"),
    path("online/callback/", OnlinePaymentCallbackView.as_view(), name="online-payment-callback"),
    path("online/orders/", OnlinePaymentOrderListView.as_view(), name="online-payment-order-list"),
    path("online/orders/<uuid:order_id>/", OnlinePaymentOrderDetailView.as_view(), name="online-payment-order-detail"),
    path("online/orders/<uuid:order_id>/reconcile/", OnlinePaymentOrderReconcileView.as_view(), name="online-payment-order-reconcile"),
    path("students/<uuid:student_id>/", StudentFeesView.as_view(), name="student-fees"),
    path("students/<uuid:student_id>/assign/", AssignStudentFeeView.as_view(), name="student-fee-assign"),
    path("students/<uuid:student_id>/fees/<uuid:fee_id>/", StudentFeeUpdateView.as_view(), name="student-fee-update"),
    path("students/<uuid:student_id>/cancel/<uuid:fee_id>/", CancelStudentFeeView.as_view(), name="student-fee-cancel"),
    path("students/<uuid:student_id>/payments/", StudentPaymentsView.as_view(), name="student-payments"),
    path("payments/", RecordPaymentView.as_view(), name="record-payment"),
    path("payments/<uuid:payment_id>/receipt/", PaymentReceiptView.as_view(), name="payment-receipt"),
    path("payments/<uuid:payment_id>/reverse/", ReversePaymentView.as_view(), name="payment-reverse"),
    path("reports/outstanding/", OutstandingReportView.as_view(), name="outstanding-report"),
    path("reports/dues/", DuesByStudentView.as_view(), name="dues-by-student"),
    path("students/<uuid:student_id>/calls/", StudentCallsView.as_view(), name="student-fee-calls"),
    path("", include(router.urls)),
]
