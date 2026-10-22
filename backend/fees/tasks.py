import logging
import time

from celery import shared_task
from django.db import transaction
from django.utils import timezone
from django_tenants.utils import get_tenant_model, schema_context

from .services import reconcile_online_payment_order

logger = logging.getLogger(__name__)

# Bounds work per tenant per run; any remainder is picked up next run.
BATCH_SIZE = 50

# settings.CELERY_TASK_TIME_LIMIT (30s) hard-kills a task that overruns it.
# The task stops starting new reconciliations after this budget and leaves the
# rest for the next run.
TIME_BUDGET_SECONDS = 20


@shared_task
def reconcile_pending_online_payments(batch_size=BATCH_SIZE, time_budget=TIME_BUDGET_SECONDS):
    """
    Periodic Celery Beat task that scans active tenant schemas for pending
    or unconfirmed OnlinePaymentOrders and reconciles them with the gateway.

    Operates across all active tenant schemas:
    - Iterates tenant schemas via schema_context() (skipping public).
    - Uses select_for_update(skip_locked=True) to prevent worker race conditions.
    - Honors TIME_BUDGET_SECONDS to avoid Celery task hard timeout kills.
    - Calls reconcile_online_payment_order() per order.
    """
    from .models import OnlinePaymentOrder

    deadline = time.monotonic() + time_budget
    summary = {
        "schemas_checked": 0,
        "processed": 0,
        "success": 0,
        "reconciliation_required": 0,
        "expired": 0,
        "errors": 0,
        "deferred": 0,
    }

    for tenant in get_tenant_model().objects.exclude(schema_name="public"):
        if time.monotonic() > deadline:
            logger.warning(
                "Time budget reached during online payment reconciliation; remaining tenants deferred."
            )
            summary["deferred"] += 1
            break

        summary["schemas_checked"] += 1
        with schema_context(tenant.schema_name):
            try:
                # Select pending orders up to batch_size, skip locked rows to avoid blocking concurrent workers
                pending_order_ids = list(
                    OnlinePaymentOrder.objects.filter(status="pending")
                    .order_by("created_at")
                    .values_list("id", flat=True)[:batch_size]
                )

                for order_id in pending_order_ids:
                    if time.monotonic() > deadline:
                        summary["deferred"] += len(pending_order_ids) - summary["processed"]
                        logger.warning(
                            "Time budget reached in schema %s; deferring remaining orders.",
                            tenant.schema_name,
                        )
                        break

                    try:
                        with transaction.atomic():
                            # Lock individual order row safely
                            order = (
                                OnlinePaymentOrder.objects.select_for_update(skip_locked=True)
                                .filter(id=order_id, status="pending")
                                .first()
                            )
                            if not order:
                                continue

                            result = reconcile_online_payment_order(order)
                            summary["processed"] += 1
                            res_status = result.get("status")
                            if res_status == "success":
                                summary["success"] += 1
                            elif res_status == "reconciliation_required":
                                summary["reconciliation_required"] += 1
                            elif res_status == "expired":
                                summary["expired"] += 1

                    except Exception as exc:
                        summary["errors"] += 1
                        logger.error(
                            "Error reconciling online payment order %s in schema %s: %s",
                            order_id,
                            tenant.schema_name,
                            exc,
                            exc_info=True,
                        )
            except Exception as schema_exc:
                summary["errors"] += 1
                logger.error(
                    "Error processing schema %s during payment reconciliation: %s",
                    tenant.schema_name,
                    schema_exc,
                    exc_info=True,
                )

    if summary["processed"] > 0 or summary["errors"] > 0:
        logger.info("reconcile_pending_online_payments finished: %s", summary)

    return summary



# The daily reminder run covers every school, so it gets its own, longer limit than the 30s default.
REMINDER_TIME_BUDGET_SECONDS = 240


@shared_task(time_limit=300, soft_time_limit=270)
def send_fee_reminders(time_budget=REMINDER_TIME_BUDGET_SECONDS):
    """
    Daily task: fee "due soon" and "overdue" alerts (see ``fees.reminders``) for every school that
    enabled them. Safe to repeat and to overlap (alerts are claimed through a unique row). A school
    that fails does not stop the others; work left when the time budget runs out is picked up by
    the next run.
    """
    from .reminders import alert_today, send_fee_reminders_for_current_school

    deadline = time.monotonic() + time_budget
    today = alert_today()
    summary = {"schools": 0, "schools_enabled": 0, "sent": 0, "already_sent": 0, "no_recipient": 0,
               "errors": 0, "deferred": 0}
    for tenant in get_tenant_model().objects.exclude(schema_name="public"):
        if time.monotonic() > deadline:
            summary["deferred"] += 1
            logger.warning("Time budget reached during fee reminders; remaining schools deferred.")
            break
        summary["schools"] += 1
        try:
            with schema_context(tenant.schema_name):
                result = send_fee_reminders_for_current_school(deadline=deadline, today=today)
        except Exception:
            summary["errors"] += 1
            logger.exception("Fee reminders failed for school schema %s.", tenant.schema_name)
            continue
        summary["schools_enabled"] += 1 if result["enabled"] else 0
        for key in ("sent", "already_sent", "no_recipient", "errors", "deferred"):
            summary[key] += result[key]
    if summary["sent"] or summary["errors"]:
        logger.info("send_fee_reminders finished: %s", summary)
    return summary
