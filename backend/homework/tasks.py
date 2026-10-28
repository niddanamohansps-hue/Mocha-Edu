import logging
from datetime import timedelta

from celery import shared_task
from django.core.cache import cache
from django_tenants.utils import get_tenant_model, schema_context

from core.dates import school_today

logger = logging.getLogger(__name__)


def remind_due_tomorrow(today=None):
    """In the current school: one notice per student (and their parents) for homework due tomorrow and not done."""
    from families.models import StudentParentRelation
    from notifications.services import notify_many
    from students.models import StudentLevel

    from .models import Homework, HomeworkProgress

    today = today or school_today()
    due = today + timedelta(days=1)
    sent = 0
    for homework in Homework.objects.filter(status=Homework.ACTIVE, due_date=due).select_related("subject"):
        key = f"homework-reminder:{homework.pk}:{due}"
        if not cache.add(key, 1, 3 * 24 * 3600):
            continue
        done = set(HomeworkProgress.objects.filter(homework=homework).exclude(done_at=None).values_list("student_id", flat=True))
        pending = [s for s in StudentLevel.objects.filter(section_id=homework.section_id, is_current=True,
                                                          student__status="active").values_list("student_id", flat=True)
                   if s not in done]
        if not pending:
            continue
        users = set(StudentLevel.objects.filter(student_id__in=pending, is_current=True)
                    .exclude(student__profile__user_id=None).values_list("student__profile__user_id", flat=True))
        users |= set(StudentParentRelation.objects.filter(student_id__in=pending)
                     .exclude(parent__profile__user_id=None).values_list("parent__profile__user_id", flat=True))
        users.discard(None)
        if users:
            notify_many(recipient_user_ids=list(users), title=f"Homework due tomorrow: {homework.subject.name}",
                        body=homework.title, category="homework", link="/dashboard/homework")
            sent += 1
    return sent


@shared_task(ignore_result=True)
def send_homework_reminders():
    total = 0
    for tenant in get_tenant_model().objects.exclude(schema_name="public"):
        try:
            with schema_context(tenant.schema_name):
                total += remind_due_tomorrow()
        except Exception:  # noqa: BLE001 - one school's problem must not stop the others
            logger.exception("Homework reminders failed for school schema %s.", tenant.schema_name)
    return total
