"""
Payment gateway set-up for a school, the list of gateways a payer can use, and the Razorpay webhook.

- GET  /api/fees/gateways/                     every supported gateway and this school's set-up (no secrets)
- PUT  /api/fees/gateways/<gateway>/           save keys, mode and on/off (manage_payment_gateways)
- POST /api/fees/gateways/<gateway>/test/      check the saved keys with the gateway
- GET  /api/fees/online/gateways/              gateways a parent or student can pay with here
- POST /api/fees/online/webhook/razorpay/      Razorpay's signed notice; triggers a server-side check
"""
import logging

from rest_framework import serializers, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.tenant_access import IsTenantMember
from core.audit import log_action
from roles.permissions import HasPermission

from .gateways import GATEWAY_INFO, PaymentConfigurationError, get_gateway_credentials
from .models import OnlinePaymentOrder, TenantPaymentGatewayConfig

logger = logging.getLogger(__name__)

WEBHOOK_PATH = "/api/fees/online/webhook/razorpay/"


def _webhook_url(request):
    return request.build_absolute_uri(WEBHOOK_PATH)


def _describe(gateway, config, request):
    info = GATEWAY_INFO[gateway]
    return {
        "gateway": gateway,
        **info,
        "configured": config is not None,
        "is_active": bool(config and config.is_active),
        "mode": config.mode if config else "test",
        "merchant_code": config.merchant_code if config else "",
        # Secrets are write-only: only whether one is saved is ever returned.
        "has_secret": bool(config and config.encrypted_secret),
        "has_webhook_secret": bool(config and config.encrypted_webhook_secret),
        "webhook_url": _webhook_url(request) if info["webhooks"] else "",
        "updated_at": config.updated_at.isoformat() if config else None,
    }


class GatewayConfigInputSerializer(serializers.Serializer):
    merchant_code = serializers.CharField(max_length=100, trim_whitespace=True)
    secret = serializers.CharField(max_length=200, required=False, allow_blank=True, trim_whitespace=True)
    webhook_secret = serializers.CharField(max_length=200, required=False, allow_blank=True, trim_whitespace=True)
    mode = serializers.ChoiceField(choices=["test", "live"])
    is_active = serializers.BooleanField()


class GatewayListView(APIView):
    def get_permissions(self):
        return [IsAuthenticated(), HasPermission("manage_payment_gateways")]

    def get(self, request):
        configs = {c.gateway: c for c in TenantPaymentGatewayConfig.objects.filter(gateway__in=GATEWAY_INFO)}
        return Response([_describe(g, configs.get(g), request) for g in GATEWAY_INFO])


class GatewayDetailView(APIView):
    def get_permissions(self):
        return [IsAuthenticated(), HasPermission("manage_payment_gateways")]

    def put(self, request, gateway):
        if gateway not in GATEWAY_INFO:
            return Response({"error": "Unknown payment gateway."}, status=status.HTTP_404_NOT_FOUND)
        serializer = GatewayConfigInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        config = TenantPaymentGatewayConfig.objects.filter(gateway=gateway).first()

        errors = {}
        if gateway == "razorpay":
            from .razorpay import key_mode

            prefix_mode = key_mode(data["merchant_code"])
            if not prefix_mode:
                errors["merchant_code"] = ["A Razorpay Key ID starts with rzp_test_ or rzp_live_."]
            elif prefix_mode != data["mode"]:
                errors["mode"] = [f"This is a {prefix_mode} key: set the mode to {prefix_mode}."]
        if not data.get("secret") and not (config and config.encrypted_secret):
            errors["secret"] = ["Enter the secret key."]
        if errors:
            return Response(errors, status=status.HTTP_400_BAD_REQUEST)

        changed = ["merchant_code", "mode", "is_active"]
        if config is None:
            config = TenantPaymentGatewayConfig(gateway=gateway)
        config.merchant_code = data["merchant_code"]
        config.mode = data["mode"]
        config.is_active = data["is_active"]
        if data.get("secret"):
            config.set_secret(data["secret"])
            changed.append("secret")
        if data.get("webhook_secret"):
            config.set_webhook_secret(data["webhook_secret"])
            changed.append("webhook_secret")
        config.save()
        log_action(
            request, action="payment_gateway_updated", model_name="TenantPaymentGatewayConfig", object_id=config.id,
            # Which fields changed, never their values.
            changes={"gateway": gateway, "fields": changed, "mode": config.mode, "is_active": config.is_active},
        )
        return Response(_describe(gateway, config, request))


class GatewayTestView(APIView):
    def get_permissions(self):
        return [IsAuthenticated(), HasPermission("manage_payment_gateways")]

    def post(self, request, gateway):
        config = TenantPaymentGatewayConfig.objects.filter(gateway=gateway).first()
        if gateway not in GATEWAY_INFO or config is None:
            return Response({"ok": False, "message": "Save the keys first."}, status=status.HTTP_400_BAD_REQUEST)
        if gateway == "razorpay":
            from .razorpay import check_keys

            ok = check_keys(config.merchant_code, config.get_secret())
            message = "Razorpay accepted these keys." if ok else "Razorpay did not accept these keys. Check the Key ID and secret."
        else:
            # eSewa has no key check call; a real (test-mode) payment is the check.
            ok, message = True, "Saved. eSewa has no key check: make a small test payment to confirm."
        return Response({"ok": ok, "message": message})


class PayableGatewaysView(APIView):
    """
    Gateways a payer can use in this school, in the order shown on the Fees page: only those the school
    set up and switched on itself. The platform-wide eSewa fallback is not offered here, so a school in
    India is never shown a gateway it did not choose.
    """

    def get_permissions(self):
        return [IsAuthenticated(), IsTenantMember()]

    def get(self, request):
        chosen = set(
            TenantPaymentGatewayConfig.objects.filter(gateway__in=GATEWAY_INFO, is_active=True)
            .values_list("gateway", flat=True)
        )
        available = []
        for gateway, info in GATEWAY_INFO.items():
            if gateway not in chosen:
                continue
            try:
                get_gateway_credentials(gateway)
            except PaymentConfigurationError:
                continue
            available.append({"gateway": gateway, "label": info["label"], "methods": info["methods"],
                              "checkout": info["checkout"]})
        return Response(available)


class RazorpayWebhookView(APIView):
    """
    Razorpay's server-to-server notice. Unauthenticated by design; only a body signed with this school's
    webhook secret is acted on, and even then nothing in it is trusted: the order is checked with
    Razorpay's API (the same reconciliation as the periodic job), which settles it exactly once.
    """

    permission_classes = [AllowAny]
    authentication_classes = []
    SETTLING_EVENTS = {"payment.captured", "order.paid"}

    def post(self, request):
        from .razorpay import RazorpayGatewayAdapter
        from .services import reconcile_online_payment_order

        event = RazorpayGatewayAdapter.verify_webhook(request.body, request.headers.get("X-Razorpay-Signature", ""))
        if event is None:
            return Response({"error": "Invalid signature."}, status=status.HTTP_400_BAD_REQUEST)
        if event.get("event") not in self.SETTLING_EVENTS:
            return Response({"status": "ignored"})

        payload = event.get("payload") or {}
        rz_order_id = ((payload.get("payment") or {}).get("entity") or {}).get("order_id") or (
            (payload.get("order") or {}).get("entity") or {}
        ).get("id")
        order = None
        if isinstance(rz_order_id, str) and rz_order_id:
            order = OnlinePaymentOrder.objects.filter(gateway="razorpay", gateway_session_id=rz_order_id).first()
        if order is None:
            return Response({"status": "unknown_order"})  # acknowledged: retrying would not help

        result = reconcile_online_payment_order(order)
        if result.get("gateway_status") == "ERROR":
            # Razorpay could not be asked just now: answer 503 so Razorpay sends the notice again.
            return Response({"status": "retry"}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        logger.info("Razorpay webhook %s for order %s: %s", event.get("event"), order.gateway_order_id, result.get("status"))
        return Response({"status": result.get("status")})
