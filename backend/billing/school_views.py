"""
A school's own billing (school domain, owner or manage_billing):

- GET  /api/billing/my/                    plan, status, paid until, autopay on/off, invoices
- POST /api/billing/my/autopay/            Razorpay Checkout parameters to authorise automatic renewal
- POST /api/billing/my/autopay/cancel/     stop renewing at the end of the paid period

And the platform's Razorpay webhook (public domain): POST /api/billing/webhook/razorpay/
"""
import logging

from django.conf import settings
from django.db import connection
from rest_framework import serializers, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.audit import log_action
from fees.gateways import PaymentGatewayError
from roles.permissions import HasPermission

from .autopay import cancel_autopay, handle_webhook, start_autopay, verify_webhook
from .models import Invoice, Subscription
from .services import BillingError, refresh_status

logger = logging.getLogger(__name__)


class InvoiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Invoice
        fields = ["id", "number", "status", "plan_name", "cycle", "period_start", "period_end", "amount",
                  "gst_percent", "gst_amount", "total", "paid_at", "razorpay_payment_id"]


def _subscription():
    tenant = getattr(connection, "tenant", None)
    sub = Subscription.objects.select_related("plan").filter(organization_id=getattr(tenant, "id", None)).first()
    if sub:
        refresh_status(sub)
    return sub


class MyBillingView(APIView):
    def get_permissions(self):
        return [IsAuthenticated(), HasPermission("manage_billing")]

    def get(self, request):
        sub = _subscription()
        if sub is None:
            return Response({"subscription": None, "invoices": []})
        return Response({
            "subscription": {
                "plan": sub.plan.name, "plan_code": sub.plan.code, "cycle": sub.cycle, "status": sub.status,
                "status_label": sub.get_status_display(), "is_legacy": sub.is_legacy,
                "trial_ends_at": sub.trial_ends_at, "paid_until": sub.paid_until, "grace_ends_at": sub.grace_ends_at,
                "can_write": sub.can_write(), "student_limit": sub.plan.student_limit,
                "autopay": bool(sub.razorpay_subscription_id) and not sub.cancel_at_period_end,
                "cancel_at_period_end": sub.cancel_at_period_end,
            },
            "invoices": InvoiceSerializer(sub.invoices.filter(status=Invoice.PAID), many=True).data,
        })


class AutopayStartView(APIView):
    def get_permissions(self):
        return [IsAuthenticated(), HasPermission("manage_billing")]

    def post(self, request):
        sub = _subscription()
        if sub is None:
            return Response({"error": "This school has no subscription."}, status=status.HTTP_404_NOT_FOUND)
        try:
            checkout = start_autopay(sub)
        except BillingError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except PaymentGatewayError as exc:
            logger.error("Autopay could not start for %s: %s", sub.pk, exc)
            return Response({"error": "Automatic renewal is not available right now."},
                            status=status.HTTP_503_SERVICE_UNAVAILABLE)
        log_action(request, action="billing_autopay_started", model_name="Subscription", object_id=sub.id,
                   changes={"cycle": sub.cycle})
        return Response({"checkout": checkout})


class AutopayCancelView(APIView):
    def get_permissions(self):
        return [IsAuthenticated(), HasPermission("manage_billing")]

    def post(self, request):
        sub = _subscription()
        if sub is None:
            return Response({"error": "This school has no subscription."}, status=status.HTTP_404_NOT_FOUND)
        try:
            cancel_autopay(sub)
        except (BillingError, PaymentGatewayError) as exc:
            logger.error("Autopay could not be cancelled for %s: %s", sub.pk, exc)
            return Response({"error": "Could not stop automatic renewal right now."},
                            status=status.HTTP_503_SERVICE_UNAVAILABLE)
        log_action(request, action="billing_autopay_cancelled", model_name="Subscription", object_id=sub.id, changes={})
        return Response({"cancel_at_period_end": True, "paid_until": sub.paid_until})


class PlatformWebhookView(APIView):
    """Razorpay's notices about school subscriptions. Only a correctly signed body is acted on."""

    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        event = verify_webhook(request.body, request.headers.get("X-Razorpay-Signature", ""))
        if event is None:
            return Response({"error": "Invalid signature."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            result = handle_webhook(event)
        except Exception:  # noqa: BLE001 - Razorpay retries on a 5xx
            logger.exception("Billing webhook %s failed.", event.get("event"))
            return Response({"status": "retry"}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        return Response({"status": result})


def _platform_order(sub, invoice, key_id, secret):
    from fees.razorpay import api_request, to_paise

    order = api_request("POST", "/orders", key_id=key_id, key_secret=secret, body={
        "amount": to_paise(invoice.total), "currency": "INR", "receipt": invoice.id.hex[:40],
        "notes": {"invoice": str(invoice.id)}})
    order_id = str(order.get("id") or "") if isinstance(order, dict) else ""
    if not order_id.startswith("order_") or order.get("amount") != to_paise(invoice.total):
        raise PaymentGatewayError("Razorpay did not create a matching order.")
    return order_id


class PayNowView(APIView):
    """
    Pays the next period now (an overdue renewal, a monthly/yearly payment without autopay, or a
    one-time purchase): a draft invoice and a Razorpay order on the platform account.
    POST {cycle?}; defaults to the subscription's cycle.
    """

    def get_permissions(self):
        return [IsAuthenticated(), HasPermission("manage_billing")]

    def post(self, request):
        from fees.razorpay import to_paise

        from .services import issue_invoice
        from .signup import platform_keys

        sub = _subscription()
        if sub is None or sub.is_legacy:
            return Response({"error": "Choose a plan first."}, status=status.HTTP_400_BAD_REQUEST)
        cycle = request.data.get("cycle") or sub.cycle
        try:
            if cycle not in ("monthly", "yearly", "one_time") or not sub.plan.offers(cycle):
                raise BillingError(f"{sub.plan.name} is not offered that way.")
            key_id, secret = platform_keys()
        except BillingError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        invoice = issue_invoice(sub, cycle=cycle)
        try:
            order_id = _platform_order(sub, invoice, key_id, secret)
        except PaymentGatewayError as exc:
            logger.error("Pay-now could not start for %s: %s", sub.pk, exc)
            invoice.status = Invoice.VOID
            invoice.save(update_fields=["status", "updated_at"])
            return Response({"error": "Online payment is not available right now."},
                            status=status.HTTP_503_SERVICE_UNAVAILABLE)
        invoice.razorpay_order_id = order_id
        invoice.save(update_fields=["razorpay_order_id", "updated_at"])
        org = sub.organization
        return Response({"invoice": str(invoice.id), "total": str(invoice.total), "checkout": {
            "key": key_id, "order_id": order_id, "amount": to_paise(invoice.total), "currency": "INR",
            "name": getattr(settings, "PLATFORM_NAME", "EduSekai"),
            "description": f"{sub.plan.name} ({cycle.replace('_', '-')})",
            "prefill": {"name": org.name, "email": org.email, "contact": org.phone}}})


class PayNowConfirmView(APIView):
    """Razorpay's signed answer for a pay-now order; the invoice is paid only after Razorpay confirms it."""

    def get_permissions(self):
        return [IsAuthenticated(), HasPermission("manage_billing")]

    def post(self, request):
        import hashlib
        import hmac
        import urllib.parse

        from fees.razorpay import api_request, to_paise

        from .services import mark_invoice_paid
        from .signup import platform_keys

        sub = _subscription()
        order_id = str(request.data.get("razorpay_order_id") or "")[:100]
        payment_id = str(request.data.get("razorpay_payment_id") or "")[:100]
        signature = str(request.data.get("razorpay_signature") or "")[:200]
        invoice = Invoice.objects.filter(subscription=sub, razorpay_order_id=order_id).first() if sub and order_id else None
        rejected = Response({"error": "Payment could not be verified."}, status=status.HTTP_400_BAD_REQUEST)
        if invoice is None or not payment_id:
            return rejected
        try:
            key_id, secret = platform_keys()
        except BillingError:
            return Response({"error": "Online payment is not available right now."},
                            status=status.HTTP_503_SERVICE_UNAVAILABLE)
        expected = hmac.new(secret.encode(), f"{order_id}|{payment_id}".encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, signature):
            return rejected
        try:
            payment = api_request("GET", f"/payments/{urllib.parse.quote(payment_id)}", key_id=key_id, key_secret=secret)
        except PaymentGatewayError:
            return Response({"status": "checking"}, status=status.HTTP_202_ACCEPTED)
        if not (isinstance(payment, dict) and payment.get("order_id") == order_id and payment.get("status") == "captured"
                and payment.get("currency") == "INR" and payment.get("amount") == to_paise(invoice.total)):
            return rejected
        try:
            invoice, _ = mark_invoice_paid(invoice.id, payment_id=payment_id, paid_amount_paise=payment["amount"])
        except BillingError:
            return rejected
        log_action(request, action="billing_paid", model_name="Invoice", object_id=invoice.id,
                   changes={"number": invoice.number, "total": str(invoice.total)})
        return Response({"status": "paid", "invoice": InvoiceSerializer(invoice).data})


class InvoicePdfView(APIView):
    def get_permissions(self):
        return [IsAuthenticated(), HasPermission("manage_billing")]

    def get(self, request, invoice_id):
        from django.http import HttpResponse

        from .pdf import render_invoice_pdf

        sub = _subscription()
        invoice = Invoice.objects.filter(id=invoice_id, subscription=sub, status=Invoice.PAID).first() if sub else None
        if invoice is None:
            return Response({"error": "Invoice not found."}, status=status.HTTP_404_NOT_FOUND)
        response = HttpResponse(render_invoice_pdf(invoice), content_type="application/pdf")
        filename = "invoice-" + invoice.number.replace("/", "-") + ".pdf"
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        return response
