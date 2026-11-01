"""Announcing an examination's date sheet to the students and parents of the classes sitting it."""
import logging

from django.conf import settings
from django.db import transaction
from django.db.models import F
from django.utils import timezone

from core.audit import log_action
from notifications.alerts import (
    dispatch_alert,
    dispatch_whatsapp_alert,
    resolve_alert_recipients,
    resolve_whatsapp_recipients,
)
from notifications.models import AlertLog

from .allocation import AllocationError, _roster
from .models import Examination, ExamSchedule

logger = logging.getLogger(__name__)
LINK = "/dashboard"


@transaction.atomic
def publish_date_sheet(examination, request=None):
    """Record a new announcement of the date sheet and queue it for sending. Returns its number."""
    examination = Examination.objects.select_for_update().get(pk=examination.pk)
    if not ExamSchedule.objects.filter(examination=examination).exists():
        raise AllocationError("Add at least one paper to this examination before publishing its date sheet.")
    Examination.objects.filter(pk=examination.pk).update(
        date_sheet_version=F("date_sheet_version") + 1, date_sheet_published_at=timezone.now()
    )
    examination.refresh_from_db()
    version = examination.date_sheet_version
    log_action(request, "date_sheet_published", "Examination", str(examination.id), {"version": version})

    from django.db import connection

    schema_name = connection.schema_name
    transaction.on_commit(lambda: _queue(schema_name, str(examination.id), version))
    return version


def _queue(schema_name, examination_id, version):
    from celery.exceptions import CeleryError
    from kombu.exceptions import KombuError

    from .tasks import send_date_sheet_alerts_task

    try:
        send_date_sheet_alerts_task.delay(schema_name, examination_id, version)
    except (CeleryError, KombuError):
        logger.warning("Could not queue the date sheet alerts for examination %s", examination_id, exc_info=True)


def send_date_sheet_alerts(examination_id, version):
    """Tell every student and linked parent of each class sitting the examination. Safe to run twice for the same
    announcement number: an alert already sent to someone is never repeated. One bad student never stops the rest."""
    examination = Examination.objects.get(pk=examination_id)
    summary = {"students": 0, "alerts": 0, "errors": 0}
    sections = {
        s.section_id: s.section
        for s in ExamSchedule.objects.filter(examination=examination).select_related("section__level")
    }
    for section in sections.values():
        for student in _roster(section.id):
            summary["students"] += 1
            name = f"{student.profile.first_name} {student.profile.last_name}".strip()
            key = f"{AlertLog.Kind.EXAM_DATE_SHEET}:{examination.id}:{version}:{student.id}"
            title = f"Date sheet: {examination.name} ({name})"[:200]
            body = (
                f"The date sheet for {examination.name} is out for {name} ({section.level.name} {section.name}). "
                f"The examinations run from {examination.start_date:%d %b %Y} to {examination.end_date:%d %b %Y}."
            )[:500]
            try:
                for recipient in resolve_alert_recipients(student):
                    result = dispatch_alert(
                        kind=AlertLog.Kind.EXAM_DATE_SHEET, dedupe_key=key, recipient=recipient, student=student,
                        title=title, body=body, link=LINK,
                    )
                    summary["alerts"] += int(result.created)
                for recipient in resolve_whatsapp_recipients(student):
                    result = dispatch_whatsapp_alert(
                        kind=AlertLog.Kind.EXAM_DATE_SHEET, dedupe_key=key, recipient=recipient, student=student,
                        template=settings.WHATSAPP_TEMPLATE_DATE_SHEET,
                        params=[name, examination.name, examination.start_date.isoformat(), examination.end_date.isoformat()],
                    )
                    summary["alerts"] += int(result.created)
            except Exception:
                summary["errors"] += 1
                logger.exception("Could not send the date sheet alert (student %s).", student.id)
    return summary
