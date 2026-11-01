"""Fee reminder alerts (Alerts Stage 2): "due soon" and "overdue" messages to the student and
their linked parents, built on ``notifications.alerts.dispatch_alert``.

Rules (all measured on the *school calendar day* in ``settings.ALERT_TIME_ZONE``, not UTC):

* Only a school that switched ``fee_reminders_enabled`` on is touched.
* Only an active fee of an active student, with a due date and an outstanding balance above 0.
* Due soon: one reminder, from ``fee_reminder_days_before`` days before the due date up to and
  including the due date (so a missed run is caught up on the next one).
* Overdue: reminder number k (0-based) is due ``1 + k * overdue_reminder_interval_days`` days after
  the due date, for k < ``max_overdue_reminders``. A run sends the reminder whose window it is in,
  never several at once, and never a reminder whose window has passed.
* Every alert is keyed by fee, due date and reminder number, so repeating a run or a second
  worker sends nothing twice; a changed due date counts as a new fee deadline.
"""
import logging
import time
from datetime import timedelta
from zoneinfo import ZoneInfo

from django.conf import settings
from django.utils import timezone
from django_tenants.utils import get_public_schema_name

from django.conf import settings as django_settings

from notifications.alerts import (
    dispatch_alert,
    dispatch_whatsapp_alert,
    resolve_alert_recipients,
    resolve_whatsapp_recipients,
)
from notifications.models import AlertLog, NotificationSettings

from .models import StudentFee
from .services import annotate_with_outstanding_balance

logger = logging.getLogger(__name__)

# Upper bound of candidate fees read per school per run; the rest waits for the next run.
CANDIDATE_LIMIT = 2000


def alert_today():
    """Today's date on the school calendar."""
    zone = ZoneInfo(getattr(settings, "ALERT_TIME_ZONE", "Asia/Kathmandu"))
    return timezone.now().astimezone(zone).date()


def _money(amount):
    return f"{amount:,.2f}"


def _due_soon_key(fee):
    return f"{AlertLog.Kind.FEE_DUE_SOON}:{fee.id}:{fee.due_date.isoformat()}"


def _overdue_key(fee, number):
    return f"{AlertLog.Kind.FEE_OVERDUE}:{fee.id}:{fee.due_date.isoformat()}:{number}"


def _overdue_number(fee, today, cfg):
    """The overdue reminder number whose window ``today`` is in, or None."""
    days_over = (today - fee.due_date).days
    if days_over < 1:
        return None
    number = (days_over - 1) // cfg.overdue_reminder_interval_days
    return number if number < cfg.max_overdue_reminders else None


def _candidates(today, cfg):
    horizon_past = cfg.max_overdue_reminders * cfg.overdue_reminder_interval_days + 1
    queryset = annotate_with_outstanding_balance(
        StudentFee.objects.filter(
            status="active",
            student__status="active",
            due_date__isnull=False,
            due_date__gte=today - timedelta(days=horizon_past),
            due_date__lte=today + timedelta(days=cfg.fee_reminder_days_before),
        )
    )
    return (
        queryset.filter(_outstanding__gt=0)
        .select_related("student__profile", "fee_head")
        .order_by("due_date", "id")[:CANDIDATE_LIMIT]
    )


def _wanted(fee, today, cfg):
    """``(kind, dedupe_key, title, body)`` for the reminder due today, or None."""
    outstanding = fee._outstanding
    due = fee.due_date.isoformat()
    name = fee.fee_head.name
    if fee.due_date >= today:
        if (fee.due_date - today).days > cfg.fee_reminder_days_before:
            return None
        title = f"Fee due soon: {name}"
        body = f"{name}: {_money(outstanding)} outstanding, due on {due}."
        return AlertLog.Kind.FEE_DUE_SOON, _due_soon_key(fee), title[:200], body[:500]
    number = _overdue_number(fee, today, cfg)
    if number is None:
        return None
    title = f"Fee overdue: {name}"
    body = f"{name}: {_money(outstanding)} outstanding, was due on {due}."
    return AlertLog.Kind.FEE_OVERDUE, _overdue_key(fee, number), title[:200], body[:500]


def _send_whatsapp_reminders(fee, student, kind, key):
    """The WhatsApp copy of a fee reminder, for parents who opted in. Never raises: a failure here must not
    stop the in-app and email reminders."""
    try:
        recipients = resolve_whatsapp_recipients(student)
        if not recipients:
            return
        template = (
            django_settings.WHATSAPP_TEMPLATE_FEE_DUE
            if kind == AlertLog.Kind.FEE_DUE_SOON
            else django_settings.WHATSAPP_TEMPLATE_FEE_OVERDUE
        )
        name = f"{student.profile.first_name} {student.profile.last_name}".strip()
        params = [name, fee.fee_head.name, _money(fee._outstanding), fee.due_date.isoformat()]
        for recipient in recipients:
            dispatch_whatsapp_alert(
                kind=kind, dedupe_key=key, recipient=recipient, student=student, template=template, params=params
            )
    except Exception:
        logger.exception("Could not queue a WhatsApp fee reminder (fee %s).", fee.id)


def send_fee_reminders_for_current_school(*, deadline=None, today=None):
    """Send the fee reminders that are due, in the current tenant schema. Returns a summary."""
    from django.db import connection

    summary = {"enabled": False, "fees_considered": 0, "sent": 0, "already_sent": 0, "no_recipient": 0,
               "errors": 0, "deferred": 0}
    if connection.schema_name == get_public_schema_name():
        raise RuntimeError("Fee reminders can only run inside a tenant schema.")
    cfg = NotificationSettings.load()
    if not cfg.fee_reminders_enabled:
        return summary
    summary["enabled"] = True
    today = today or alert_today()

    work = []
    for fee in _candidates(today, cfg):
        wanted = _wanted(fee, today, cfg)
        if wanted is not None:
            work.append((fee, wanted))
    summary["fees_considered"] = len(work)
    if not work:
        return summary

    sent_before = set(
        AlertLog.objects.filter(dedupe_key__in=[w[1][1] for w in work]).values_list("dedupe_key", "recipient_user_id")
    )
    recipients_by_student = {}
    for index, (fee, (kind, key, title, body)) in enumerate(work):
        if deadline is not None and time.monotonic() > deadline:
            summary["deferred"] = len(work) - index
            break
        student = fee.student
        _send_whatsapp_reminders(fee, student, kind, key)
        if student.id not in recipients_by_student:
            recipients_by_student[student.id] = resolve_alert_recipients(student)
        recipients = recipients_by_student[student.id]
        if not recipients:
            summary["no_recipient"] += 1
            continue
        for recipient in recipients:
            if (key, recipient.user_id) in sent_before:
                summary["already_sent"] += 1
                continue
            try:
                result = dispatch_alert(
                    kind=kind, dedupe_key=key, recipient=recipient, student=student, title=title, body=body,
                )
            except Exception:
                summary["errors"] += 1
                logger.exception("Could not send a fee reminder (fee %s).", fee.id)
                continue
            summary["sent" if result.created else "already_sent"] += 1
    return summary
