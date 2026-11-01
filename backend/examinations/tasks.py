from celery import shared_task
from django_tenants.utils import schema_context


@shared_task(ignore_result=True)
def send_date_sheet_alerts_task(schema_name, examination_id, version):
    """Runs in a worker, which has no tenant of its own, so the school's schema is entered explicitly."""
    from .date_sheet import send_date_sheet_alerts

    with schema_context(schema_name):
        return send_date_sheet_alerts(examination_id, version)


@shared_task
def remind_pending_marks():
    """Daily, in every school: remind teachers whose marks are due within a day or already late. Iterates the
    school schemas itself because a periodic task has no tenant of its own."""
    from django_tenants.utils import get_tenant_model

    from .progress import remind_all_schools

    reminded = 0
    for tenant in get_tenant_model().objects.exclude(schema_name="public"):
        with schema_context(tenant.schema_name):
            reminded += remind_all_schools()["teachers"]
    return reminded
