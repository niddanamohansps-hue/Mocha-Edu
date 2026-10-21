import logging
import time

from celery import shared_task

from . import services

logger = logging.getLogger(__name__)

BATCH_SIZE = 20
# CELERY_TASK_TIME_LIMIT (30s) hard-kills a task that overruns it. A gateway call can take up to
# its own 10s timeout, so no new call starts after this budget; the rest waits for the next run.
TIME_BUDGET_SECONDS = 15


@shared_task
def reconcile_signup_payments(batch_size=BATCH_SIZE, time_budget=TIME_BUDGET_SECONDS):
    """
    Periodic task for the paid-signup flow (public schema):
      1. expire unpaid signups past their reservation, release stalled provisioning claims;
      2. ask eSewa about unpaid-looking signups (money can arrive after the tab was closed);
      3. queue institution setup for paid signups that still have none (a separate task, because
         creating a tenant takes longer than this task's time limit);
      4. discard the stored password of long-expired unpaid signups;
      5. announce paid signups that need a person.
    Every step is safe to repeat and to run concurrently.
    """
    deadline = time.monotonic() + time_budget
    summary = {
        "expired": services.expire_stale_reservations(),
        "stalled_released": services.recover_stalled_provisioning(),
    }
    gateway, ready = services.reconcile_with_gateway(batch_size=batch_size, deadline=deadline)
    summary["gateway"] = gateway
    to_provision = list(dict.fromkeys(ready + services.provisioning_retry_candidates(batch_size)))
    for payment_pk in to_provision:
        provision_signup_payment.delay(payment_pk)
    summary["provisioning_queued"] = len(to_provision)
    summary["data_discarded"] = services.discard_expired_signup_data()
    summary["attention_notified"] = services.notify_attention(batch_size)
    if any((summary["expired"], gateway["checked"], len(to_provision), summary["attention_notified"])):
        logger.info("reconcile_signup_payments finished: %s", summary)
    return summary


@shared_task(time_limit=900, soft_time_limit=840)
def provision_signup_payment(payment_pk):
    """Create the institution for one paid signup. Own, longer time limit: tenant creation runs
    schema migrations. Safe to run twice: only one run can claim the payment."""
    outcome, _ = services.provision(payment_pk)
    return outcome
