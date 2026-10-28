"""
Automatic renewal (monthly / yearly) through Razorpay Subscriptions, on the platform's Razorpay account.

- ``razorpay_plan_id`` creates (once) the Razorpay plan for a Plan + cycle, priced with GST, and stores it.
- ``start_autopay`` creates a Razorpay subscription for a school and returns Checkout parameters: the school
  authorises a UPI AutoPay / card mandate once, and Razorpay charges each period by itself.
- ``handle_webhook`` acts on Razorpay's signed notices. ``subscription.charged`` becomes a paid invoice that
  extends access (idempotent per payment id); halted / cancelled stop renewal (access then runs out at
  ``paid_until`` and follows the usual grace -> read-only path). Nothing in a notice is trusted beyond the
  signature: amounts are checked against the plan, subscriptions against the stored id.
- ``cancel_autopay`` stops renewal at the end of the paid period.
"""
import hashlib
import hmac
import json
import logging
import urllib.parse

from django.conf import settings
from django.db import transaction

from fees.razorpay import api_request, to_paise

from .models import MONTHLY, YEARLY, Subscription
from .services import BillingError, gst_for, issue_invoice, mark_invoice_paid
from .signup import platform_keys

logger = logging.getLogger(__name__)

PERIOD = {MONTHLY: "monthly", YEARLY: "yearly"}
# How many renewals a mandate covers (Razorpay needs a number): 10 years either way.
TOTAL_COUNT = {MONTHLY: 120, YEARLY: 10}
MAX_WEBHOOK_BYTES = 65536


def period_total(plan, cycle):
    price = plan.price_for(cycle)
    if price is None or cycle not in PERIOD:
        raise BillingError("Automatic renewal is only for monthly or yearly plans.")
    return price + gst_for(price, plan.gst_percent)


def razorpay_plan_id(plan, cycle):
    field = "razorpay_monthly_plan_id" if cycle == MONTHLY else "razorpay_yearly_plan_id"
    amount_field = "razorpay_monthly_amount" if cycle == MONTHLY else "razorpay_yearly_amount"
    amount = to_paise(period_total(plan, cycle))
    existing = getattr(plan, field)
    if existing and getattr(plan, amount_field) == amount:
        return existing
    key_id, secret = platform_keys()
    created = api_request("POST", "/plans", key_id=key_id, key_secret=secret, body={
        "period": PERIOD[cycle], "interval": 1,
        "item": {"name": f"{plan.name} ({PERIOD[cycle]})", "amount": amount,
                 "currency": "INR"},
        "notes": {"plan": plan.code},
    })
    plan_id = str(created.get("id") or "") if isinstance(created, dict) else ""
    if not plan_id.startswith("plan_"):
        raise BillingError("Razorpay did not create the plan.")
    setattr(plan, field, plan_id)
    setattr(plan, amount_field, amount)
    plan.save(update_fields=[field, amount_field, "updated_at"])
    return plan_id


def start_autopay(subscription):
    """Razorpay Checkout parameters for authorising automatic renewal of this school's subscription."""
    if subscription.is_legacy:
        raise BillingError("This school is on a legacy plan; choose a plan first.")
    if subscription.cycle not in PERIOD:
        raise BillingError("Automatic renewal is only for monthly or yearly plans.")
    key_id, secret = platform_keys()
    body = {
        "plan_id": razorpay_plan_id(subscription.plan, subscription.cycle),
        "total_count": TOTAL_COUNT[subscription.cycle],
        "customer_notify": 1,
        "notes": {"subscription": str(subscription.id), "school": subscription.organization.schema_name},
    }
    # Already paid ahead: the first automatic charge is when the paid period ends.
    if subscription.paid_until:
        body["start_at"] = int(subscription.paid_until.timestamp())
    created = api_request("POST", "/subscriptions", key_id=key_id, key_secret=secret, body=body)
    rz_id = str(created.get("id") or "") if isinstance(created, dict) else ""
    if not rz_id.startswith("sub_"):
        raise BillingError("Razorpay did not create the subscription.")
    subscription.razorpay_subscription_id = rz_id
    subscription.autopay_amount_paise = to_paise(period_total(subscription.plan, subscription.cycle))
    subscription.cancel_at_period_end = False
    subscription.save(update_fields=["razorpay_subscription_id", "autopay_amount_paise", "cancel_at_period_end",
                                     "updated_at"])
    return {
        "key": key_id,
        "subscription_id": rz_id,
        "name": getattr(settings, "PLATFORM_NAME", "EduSekai"),
        "description": f"{subscription.plan.name}, renews {PERIOD[subscription.cycle]}",
        "prefill": {"name": subscription.organization.name, "email": subscription.organization.email,
                    "contact": subscription.organization.phone},
    }


def cancel_autopay(subscription):
    """Stops renewal; access continues to the end of what is paid."""
    if subscription.razorpay_subscription_id:
        key_id, secret = platform_keys()
        api_request("POST", f"/subscriptions/{urllib.parse.quote(subscription.razorpay_subscription_id)}/cancel",
                    key_id=key_id, key_secret=secret, body={"cancel_at_cycle_end": 1})
    subscription.cancel_at_period_end = True
    subscription.save(update_fields=["cancel_at_period_end", "updated_at"])


def verify_webhook(raw_body, signature):
    secret = getattr(settings, "PLATFORM_RAZORPAY_WEBHOOK_SECRET", "")
    if not secret or not raw_body or len(raw_body) > MAX_WEBHOOK_BYTES or not signature or len(signature) > 200:
        return None
    expected = hmac.new(secret.encode(), raw_body, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, signature):
        return None
    try:
        event = json.loads(raw_body.decode("utf-8"))
    except Exception:  # noqa: BLE001
        return None
    return event if isinstance(event, dict) else None


def handle_webhook(event):
    """Returns a short status string. Raises nothing for unknown or irrelevant events."""
    name = event.get("event")
    payload = event.get("payload") or {}
    rz_sub = (payload.get("subscription") or {}).get("entity") or {}
    subscription = Subscription.objects.select_related("plan", "organization").filter(
        razorpay_subscription_id=str(rz_sub.get("id") or "") or "-").first()
    if subscription is None:
        return "unknown_subscription"

    if name == "subscription.charged":
        payment = (payload.get("payment") or {}).get("entity") or {}
        payment_id = str(payment.get("id") or "")
        # The mandate's own amount, so a later price change does not reject what the school agreed to pay.
        expected = subscription.autopay_amount_paise or to_paise(period_total(subscription.plan, subscription.cycle))
        if not payment_id or payment.get("status") != "captured" or payment.get("currency") != "INR" \
                or payment.get("amount") != expected:
            logger.warning("Ignored a renewal charge for %s that does not match its plan.", subscription.pk)
            return "ignored"
        from .models import Invoice

        if Invoice.objects.filter(razorpay_payment_id=payment_id).exists():
            return "already_recorded"
        with transaction.atomic():
            invoice = issue_invoice(subscription, amount_paise=expected)
            mark_invoice_paid(invoice.id, payment_id=payment_id, paid_amount_paise=payment["amount"])
        return "renewed"

    if name == "subscription.halted":
        # Razorpay gave up retrying the charge. Nothing changes now: when the paid period ends the
        # school gets the usual grace days, then read-only, and can pay or re-authorise any time.
        logger.warning("Autopay halted for %s (payments failing).", subscription.pk)
        return "payment_failing"

    if name in ("subscription.cancelled", "subscription.completed"):
        subscription.cancel_at_period_end = True
        subscription.save(update_fields=["cancel_at_period_end", "updated_at"])
        return "renewal_stopped"

    if name in ("subscription.activated", "subscription.authenticated", "subscription.resumed"):
        subscription.cancel_at_period_end = False
        subscription.save(update_fields=["cancel_at_period_end", "updated_at"])
        return "renewal_on"
    return "ignored"
