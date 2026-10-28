"""
Signing up a school on a plan (public site, no account yet).

- A plan with a free trial: no payment; the school is created at once on a trial subscription.
- Otherwise the first period is paid through the PLATFORM's Razorpay account (keys in settings, never a
  school's): the browser gets Razorpay Checkout parameters, and ``confirm_razorpay_signup`` checks
  Razorpay's signature and asks Razorpay for the payment (captured, exact amount, INR) before the school
  is created through the existing signup state machine (payments.services).
- ``on_school_provisioned`` (called once the school exists) creates its subscription and, for a paid
  signup, the paid GST invoice.
"""
import hashlib
import hmac
import logging
import urllib.parse

from django.conf import settings

from fees.gateways import PaymentGatewayError
from fees.razorpay import api_request, key_mode, to_paise

from .models import ONE_TIME, Plan, Subscription
from .services import BillingError, gst_for, issue_invoice, mark_invoice_paid, start_subscription

logger = logging.getLogger(__name__)


class SignupPaymentRejected(Exception):
    """The confirmation could not be verified. Deliberately says nothing about which check failed."""


def platform_keys():
    key_id = getattr(settings, "PLATFORM_RAZORPAY_KEY_ID", "")
    secret = getattr(settings, "PLATFORM_RAZORPAY_KEY_SECRET", "")
    if not key_mode(key_id) or not secret:
        raise BillingError("Online signup payment is not configured.")
    return key_id, secret


def signup_total(plan, cycle):
    """Price for the first period, GST included."""
    price = plan.price_for(cycle)
    if price is None:
        raise BillingError("This plan is not offered on that billing cycle.")
    return price + gst_for(price, plan.gst_percent)


def resolve_plan(code, cycle):
    plan = Plan.objects.filter(code=code, is_public=True).first()
    if plan is None:
        raise BillingError("Choose a plan.")
    if cycle not in ("monthly", "yearly", "one_time") or not plan.offers(cycle):
        raise BillingError(f"{plan.name} is not offered that way.")
    return plan


def razorpay_checkout(payment):
    """Creates the Razorpay order for a pending signup and returns what Checkout needs."""
    key_id, secret = platform_keys()
    order = api_request(
        "POST", "/orders", key_id=key_id, key_secret=secret,
        body={"amount": to_paise(payment.amount), "currency": "INR", "receipt": payment.transaction_uuid.hex[:40],
              "notes": {"signup": payment.subdomain}},
    )
    order_id = str(order.get("id") or "") if isinstance(order, dict) else ""
    if not order_id.startswith("order_") or order.get("amount") != to_paise(payment.amount):
        raise PaymentGatewayError("Razorpay did not create a matching order.")
    payment.gateway = "razorpay"
    payment.gateway_order_id = order_id
    payment.save(update_fields=["gateway", "gateway_order_id", "updated_at"])
    return {
        "gateway": "razorpay",
        "key": key_id,
        "order_id": order_id,
        "amount": to_paise(payment.amount),
        "currency": "INR",
        "name": getattr(settings, "PLATFORM_NAME", "EduSekai"),
        "description": f"{payment.plan.name} ({cycle_label(payment.cycle)}) for {payment.organization_name}",
        "prefill": {"name": payment.organization_name, "email": payment.email, "contact": payment.phone},
    }


def confirm_razorpay_signup(*, razorpay_order_id, razorpay_payment_id, razorpay_signature):
    """Returns the signup Payment once Razorpay confirms it was paid in full; raises otherwise."""
    from payments.models import Payment

    key_id, secret = platform_keys()
    values = (razorpay_order_id, razorpay_payment_id, razorpay_signature)
    if not all(isinstance(v, str) and 0 < len(v) <= 100 for v in values):
        raise SignupPaymentRejected()
    payment = Payment.objects.filter(gateway="razorpay", gateway_order_id=razorpay_order_id).first()
    if payment is None:
        raise SignupPaymentRejected()
    expected = hmac.new(secret.encode(), f"{razorpay_order_id}|{razorpay_payment_id}".encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, razorpay_signature):
        raise SignupPaymentRejected()
    try:
        rz_payment = api_request("GET", f"/payments/{urllib.parse.quote(razorpay_payment_id)}",
                                 key_id=key_id, key_secret=secret)
    except PaymentGatewayError:
        logger.warning("Razorpay could not be asked about signup %s; the reconciliation job will retry.", payment.pk)
        return payment, False
    ok = (
        isinstance(rz_payment, dict)
        and rz_payment.get("id") == razorpay_payment_id
        and rz_payment.get("order_id") == razorpay_order_id
        and rz_payment.get("currency") == "INR"
        and rz_payment.get("amount") == to_paise(payment.amount)
        and rz_payment.get("status") == "captured"
    )
    if not ok:
        raise SignupPaymentRejected()
    return payment, True


def on_school_provisioned(payment, organization):
    """The new school's subscription (and, for a paid signup, its paid invoice). Safe to call again."""
    if payment.plan_id is None or Subscription.objects.filter(organization=organization).exists():
        return
    subscription = start_subscription(organization, payment.plan, payment.cycle)
    if payment.amount and payment.gateway_reference and payment.gateway_reference != "trial":
        invoice = issue_invoice(subscription)
        mark_invoice_paid(invoice.id, payment_id=payment.gateway_reference,
                          paid_amount_paise=to_paise(payment.amount))


def cycle_label(cycle):
    return {"monthly": "monthly", "yearly": "yearly", ONE_TIME: "one-time"}.get(cycle, cycle)
