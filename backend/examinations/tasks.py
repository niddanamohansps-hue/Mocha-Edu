from celery import shared_task
from django_tenants.utils import schema_context


@shared_task(ignore_result=True)
def send_date_sheet_alerts_task(schema_name, examination_id, version):
    """Runs in a worker, which has no tenant of its own, so the school's schema is entered explicitly."""
    from .date_sheet import send_date_sheet_alerts

    with schema_context(schema_name):
        return send_date_sheet_alerts(examination_id, version)
