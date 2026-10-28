"""
Billing rules, independent of any gateway:

- start_subscription: a new school's subscription (trial, or waiting for its first payment).
- issue_invoice: a draft invoice for the next period of a subscription (amount + GST).
- mark_invoice_paid: the only way money changes access. Idempotent per gateway payment id; numbers the
  invoice, then moves ``paid_until`` forward from the later of now and the old ``paid_until``.
- refresh_status: trial -> pending/past due -> read-only as time passes (run daily, and on read).
"""
from datetime import timedelta
from decimal import ROUND_HALF_UP, Decimal

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from .models import MONTHLY, ONE_TIME, YEARLY, Invoice, InvoiceCounter, Plan, Subscription

GRACE_DAYS_DEFAULT = 7
CENT = Decimal("0.01")


class BillingError(Exception):
    """A request that cannot be billed as asked (e.g. a cycle the plan does not offer)."""


def grace_days():
    return int(getattr(settings, "BILLING_GRACE_DAYS", GRACE_DAYS_DEFAULT))


def period_length(cycle, plan):
    """How long one payment buys. None = for life."""
    if cycle == MONTHLY:
        return timedelta(days=30)
    if cycle == YEARLY:
        return timedelta(days=365)
    return timedelta(days=plan.one_time_validity_days) if plan.one_time_validity_days else None


def gst_for(amount, percent):
    return (Decimal(amount) * Decimal(percent) / 100).quantize(CENT, rounding=ROUND_HALF_UP)


def financial_year(moment):
    """Indian financial year label for a date: April 2026 - March 2027 is "2026-27"."""
    local = timezone.localtime(moment)
    start = local.year if local.month >= 4 else local.year - 1
    return f"{start}-{str(start + 1)[-2:]}"


def _next_invoice_number(moment):
    fy = financial_year(moment)
    counter, _ = InvoiceCounter.objects.select_for_update().get_or_create(financial_year=fy)
    counter.last_number += 1
    counter.save(update_fields=["last_number"])
    prefix = getattr(settings, "BILLING_INVOICE_PREFIX", "ES")
    return f"{prefix}/{fy}/{counter.last_number:05d}"


def start_subscription(organization, plan, cycle, *, now=None):
    """The subscription of a school that has just signed up."""
    now = now or timezone.now()
    if not plan.offers(cycle):
        raise BillingError(f"{plan.name} is not offered {dict(Subscription._meta.get_field('cycle').choices)[cycle].lower()}.")
    subscription = Subscription(organization=organization, plan=plan, cycle=cycle)
    if plan.trial_days:
        subscription.status = Subscription.TRIAL
        subscription.trial_ends_at = now + timedelta(days=plan.trial_days)
    else:
        subscription.status = Subscription.PENDING
    subscription.save()
    return subscription


def issue_invoice(subscription, *, now=None, cycle=None, plan=None):
    """A draft invoice for the period that starts when the current one ends (or now, if that is later)."""
    now = now or timezone.now()
    plan = plan or subscription.plan
    cycle = cycle or subscription.cycle
    amount = plan.price_for(cycle)
    if amount is None:
        raise BillingError("This plan is not offered on that billing cycle.")
    start = max(now, subscription.paid_until) if subscription.paid_until else now
    length = period_length(cycle, plan)
    org = subscription.organization
    gst = gst_for(amount, plan.gst_percent)
    from .gst import split

    cgst, sgst, igst, pos = split(gst, subscription.billing_state)
    return Invoice.objects.create(
        subscription=subscription, plan_name=plan.name, cycle=cycle,
        period_start=start, period_end=start + length if length else None,
        amount=amount, gst_percent=plan.gst_percent, gst_amount=gst, total=amount + gst,
        billed_name=org.name, billed_email=org.email, billed_address=org.address,
        billed_gstin=subscription.billing_gstin, place_of_supply=pos,
        cgst_amount=cgst, sgst_amount=sgst, igst_amount=igst,
    )


def mark_invoice_paid(invoice_id, *, payment_id, paid_amount_paise=None, now=None):
    """
    Records a confirmed payment for an invoice and extends access. Safe to call again with the same
    payment id (returns the invoice unchanged). A different amount than the invoice total is refused.
    """
    now = now or timezone.now()
    with transaction.atomic():
        invoice = Invoice.objects.select_for_update().select_related("subscription__plan").get(id=invoice_id)
        if invoice.status == Invoice.PAID:
            return invoice, False
        if paid_amount_paise is not None and paid_amount_paise != int(invoice.total * 100):
            raise BillingError("The amount paid does not match the invoice.")
        if Invoice.objects.filter(razorpay_payment_id=payment_id).exclude(id=invoice.id).exists():
            raise BillingError("This payment has already been used for another invoice.")

        subscription = Subscription.objects.select_for_update().get(id=invoice.subscription_id)
        # The period runs from when it was due (or now, if access had already lapsed), so paying late
        # never shortens what was paid for, and paying early never loses the remaining days.
        start = max(now, subscription.paid_until) if subscription.paid_until else now
        length = period_length(invoice.cycle, subscription.plan)
        invoice.period_start = start
        invoice.period_end = start + length if length else None
        invoice.status = Invoice.PAID
        invoice.razorpay_payment_id = payment_id
        invoice.paid_at = now
        invoice.number = _next_invoice_number(now)
        invoice.save()

        subscription.cycle = invoice.cycle
        subscription.status = Subscription.ACTIVE
        subscription.paid_until = invoice.period_end
        subscription.grace_ends_at = None
        subscription.save()
    return invoice, True


def refresh_status(subscription, *, now=None):
    """Moves a subscription along as time passes. Returns True when its status changed."""
    now = now or timezone.now()
    before = subscription.status
    if subscription.is_legacy or subscription.status == Subscription.CANCELLED:
        return False
    if subscription.status == Subscription.TRIAL and subscription.trial_ends_at and now >= subscription.trial_ends_at:
        subscription.status = Subscription.PAST_DUE
        subscription.grace_ends_at = subscription.trial_ends_at + timedelta(days=grace_days())
    elif subscription.status == Subscription.ACTIVE and subscription.paid_until and now >= subscription.paid_until:
        if subscription.cancel_at_period_end:
            subscription.status = Subscription.CANCELLED
        else:
            subscription.status = Subscription.PAST_DUE
            subscription.grace_ends_at = subscription.paid_until + timedelta(days=grace_days())
    if subscription.status == Subscription.PAST_DUE and subscription.grace_ends_at and now >= subscription.grace_ends_at:
        subscription.status = Subscription.READ_ONLY
    if subscription.status != before:
        subscription.save(update_fields=["status", "grace_ends_at", "updated_at"])
        return True
    return False


def plans_for_signup():
    return Plan.objects.filter(is_public=True)


__all__ = [
    "MONTHLY", "YEARLY", "ONE_TIME", "BillingError", "issue_invoice", "mark_invoice_paid",
    "refresh_status", "start_subscription", "financial_year", "gst_for", "period_length", "plans_for_signup",
]
