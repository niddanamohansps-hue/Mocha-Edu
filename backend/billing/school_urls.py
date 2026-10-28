from django.urls import path

from .school_views import (
    AutopayCancelView,
    AutopayStartView,
    GstDetailsView,
    InvoicePdfView,
    MyBillingView,
    PayNowConfirmView,
    PayNowView,
)

urlpatterns = [
    path("my/", MyBillingView.as_view(), name="billing-my"),
    path("my/autopay/", AutopayStartView.as_view(), name="billing-autopay"),
    path("my/autopay/cancel/", AutopayCancelView.as_view(), name="billing-autopay-cancel"),
    path("my/gst/", GstDetailsView.as_view(), name="billing-gst"),
    path("my/pay/", PayNowView.as_view(), name="billing-pay"),
    path("my/pay/confirm/", PayNowConfirmView.as_view(), name="billing-pay-confirm"),
    path("my/invoices/<uuid:invoice_id>/pdf/", InvoicePdfView.as_view(), name="billing-invoice-pdf"),
]
