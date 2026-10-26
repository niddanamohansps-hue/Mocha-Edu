"""Absence alerts (Alerts Stage 3): tell a student and their linked parents when the student is
marked absent, built on ``notifications.alerts.dispatch_alert``.

Rules:

* Only a school that switched ``absence_alerts_enabled`` on is touched.
* Only a mark of "absent" for an active student. Leave, late and half day never alert.
* Only for a recent school day (today, or up to ``MAX_AGE_DAYS`` days back, on the school
  calendar), so correcting an old register months later does not message anyone.
* One alert per student per day (key ``absence:<student>:<date>``), so saving the register again,
  or editing it, never repeats a message. A student first marked present and later corrected to
  absent is alerted then. An alert is not taken back if the mark is later corrected to present.
* Runs after the attendance save has committed and never fails it: any error is logged only.
"""
import logging

from django.db import connection, transaction
from django_tenants.utils import get_public_schema_name

from notifications.alerts import dispatch_alert, resolve_alert_recipients
from notifications.models import AlertLog, NotificationSettings

logger = logging.getLogger(__name__)

MAX_AGE_DAYS = 2
LINK = "/dashboard/attendance/history"


def _key(student_id, day):
    return f"{AlertLog.Kind.ABSENCE}:{student_id}:{day.isoformat()}"


def send_absence_alerts_for_session(session_id, *, today=None):
    """Send the absence alerts due for one saved register. Returns a summary."""
    from fees.reminders import alert_today

    from .models import AttendanceSession, StudentAttendance

    summary = {"enabled": False, "absent": 0, "sent": 0, "already_sent": 0, "no_recipient": 0, "errors": 0}
    if connection.schema_name == get_public_schema_name():
        raise RuntimeError("Absence alerts can only run inside a tenant schema.")
    if not NotificationSettings.load().absence_alerts_enabled:
        return summary
    summary["enabled"] = True

    session = AttendanceSession.objects.filter(id=session_id).first()
    if session is None:
        return summary
    today = today or alert_today()
    age = (today - session.date).days
    if age < 0 or age > MAX_AGE_DAYS:
        return summary

    marks = StudentAttendance.objects.filter(
        session=session, status="absent", student__status="active"
    ).select_related("student__profile")
    when = session.date.strftime("%d %b %Y")
    for mark in marks:
        student = mark.student
        summary["absent"] += 1
        recipients = resolve_alert_recipients(student)
        if not recipients:
            summary["no_recipient"] += 1
            continue
        name = f"{student.profile.first_name} {student.profile.last_name}".strip()
        title = f"{name} was absent on {when}"[:200]
        body = f"{name} was marked absent on {when}. If this is a mistake, please contact the school."[:500]
        for recipient in recipients:
            try:
                result = dispatch_alert(
                    kind=AlertLog.Kind.ABSENCE,
                    dedupe_key=_key(student.id, session.date),
                    recipient=recipient,
                    student=student,
                    title=title,
                    body=body,
                    link=LINK,
                )
            except Exception:
                summary["errors"] += 1
                logger.exception("Could not send an absence alert (student %s).", student.id)
                continue
            summary["sent" if result.created else "already_sent"] += 1
    return summary


def queue_absence_alerts(session_id):
    """Send the session's absence alerts once the surrounding transaction has committed."""

    def _run():
        try:
            send_absence_alerts_for_session(session_id)
        except Exception:
            logger.exception("Absence alerts failed for session %s.", session_id)

    transaction.on_commit(_run)
