"""Payment receipt alerts (Alerts Stage 4): tell the student and their linked parents that a
payment was received, built on ``notifications.alerts.dispatch_alert``.

Rules:

* Only a school that switched ``payment_receipts_enabled`` on is touched.
* Only a completed payment (a reversal is never announced as a receipt).
* One alert per payment (key ``payment_receipt:<payment>``), so a retry sends nothing twice.
* Runs after the payment has committed and never fails it: any error is logged only.
"""
import logging

from django.db import connection, transaction
from django_tenants.utils import get_public_schema_name

from core.dates import school_date
from notifications.alerts import dispatch_alert, resolve_alert_recipients
from notifications.models import AlertLog, NotificationSettings

logger = logging.getLogger(__name__)

LINK = "/dashboard/fees/my-fees"


def _key(payment):
    return f"{AlertLog.Kind.PAYMENT_RECEIPT}:{payment.id}"


def send_payment_receipt(payment_id):
    """Send the receipt alert for one payment. Returns a summary."""
    from .models import Payment

    summary = {"enabled": False, "sent": 0, "already_sent": 0, "no_recipient": 0, "errors": 0}
    if connection.schema_name == get_public_schema_name():
        raise RuntimeError("Payment receipts can only run inside a tenant schema.")
    if not NotificationSettings.load().payment_receipts_enabled:
        return summary
    summary["enabled"] = True

    payment = (
        Payment.objects.filter(id=payment_id, status="completed")
        .select_related("student__profile")
        .first()
    )
    if payment is None:
        return summary
    student = payment.student
    recipients = resolve_alert_recipients(student)
    if not recipients:
        summary["no_recipient"] += 1
        return summary

    name = f"{student.profile.first_name} {student.profile.last_name}".strip()
    heads = sorted({a.student_fee.fee_head.name for a in payment.allocations.select_related("student_fee__fee_head")})
    paid_for = f" for {', '.join(heads)}" if heads else ""
    title = f"Payment received: receipt {payment.receipt_number}"[:200]
    body = (
        f"We received {payment.amount:,.2f} for {name}{paid_for} on "
        f"{school_date(payment.created_at):%d %b %Y}. Receipt number {payment.receipt_number}."
    )[:500]
    for recipient in recipients:
        try:
            result = dispatch_alert(
                kind=AlertLog.Kind.PAYMENT_RECEIPT,
                dedupe_key=_key(payment),
                recipient=recipient,
                student=student,
                title=title,
                body=body,
                link=LINK,
            )
        except Exception:
            summary["errors"] += 1
            logger.exception("Could not send a payment receipt (payment %s).", payment.id)
            continue
        summary["sent" if result.created else "already_sent"] += 1
    return summary


def queue_payment_receipt(payment_id):
    """Send the receipt alert once the surrounding transaction has committed."""

    def _run():
        try:
            send_payment_receipt(payment_id)
        except Exception:
            logger.exception("Payment receipt failed for payment %s.", payment_id)

    transaction.on_commit(_run)
