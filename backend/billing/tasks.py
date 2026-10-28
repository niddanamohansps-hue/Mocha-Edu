from datetime import timedelta

from celery import shared_task
from django.core.cache import cache
from django.utils import timezone
from django_tenants.utils import tenant_context

from .models import Subscription
from .services import refresh_status

REMIND_DAYS = (7, 1)
SENT_KEEP_SECONDS = 40 * 24 * 3600


@shared_task(ignore_result=True)
def refresh_subscriptions():
    """Daily: trials and unpaid periods move on to grace, then read-only (data is never deleted)."""
    changed = 0
    for sub in Subscription.objects.exclude(status=Subscription.CANCELLED).filter(is_legacy=False):
        before = sub.status
        if refresh_status(sub):
            changed += 1
            if sub.status == Subscription.READ_ONLY and before != Subscription.READ_ONLY:
                _remind(sub, "read_only", None)
    send_renewal_reminders()
    return changed


def _due(sub):
    """(what ends, when) for a school that has to act, or None."""
    if sub.status == Subscription.TRIAL:
        return "trial", sub.trial_ends_at
    if sub.status == Subscription.ACTIVE and sub.paid_until and (sub.cancel_at_period_end or not sub.razorpay_subscription_id):
        return "period", sub.paid_until  # no autopay (or autopay stopped): someone has to pay
    if sub.status == Subscription.PAST_DUE:
        return "grace", sub.grace_ends_at
    return None


def send_renewal_reminders(now=None):
    now = now or timezone.now()
    sent = 0
    for sub in Subscription.objects.select_related("organization", "plan").filter(is_legacy=False).exclude(
            status__in=[Subscription.CANCELLED, Subscription.READ_ONLY]):
        due = _due(sub)
        if not due or not due[1]:
            continue
        days = (due[1] - now).days
        if days in REMIND_DAYS or (due[0] == "grace" and days in (3, 1)):
            sent += _remind(sub, due[0], due[1], days)
    return sent


MESSAGES = {
    "trial": ("Your free trial ends in {days} day{s}", "The EduSekai free trial for {school} ends on {date}. Pay on the Billing page to keep using it without a break."),
    "period": ("Your EduSekai plan ends in {days} day{s}", "{school}'s {plan} plan is paid until {date}. Pay on the Billing page, or turn on automatic renewal, so nothing stops."),
    "grace": ("Payment overdue: {days} day{s} before read-only", "{school}'s EduSekai payment is overdue. On {date} the school becomes read-only (nothing is deleted). Pay on the Billing page to avoid it."),
    "read_only": ("Your school is now read-only", "{school}'s EduSekai payment is overdue, so the school is read-only: everyone can still see everything, but nothing can be changed. Pay on the Billing page to unlock it at once."),
}


def _remind(sub, kind, when, days=0):
    """In-app notice to the school's owners and an email to the school. Sent once per kind, date and day count."""
    key = f"billing-reminder:{sub.pk}:{kind}:{when.date() if when else ''}:{days}"
    if not cache.add(key, 1, SENT_KEEP_SECONDS):
        return 0
    title_t, body_t = MESSAGES[kind]
    words = {"days": days, "s": "" if days == 1 else "s", "school": sub.organization.name, "plan": sub.plan.name,
             "date": timezone.localtime(when).strftime("%d %b %Y") if when else ""}
    title, body = title_t.format(**words), body_t.format(**words)
    from notifications.services import notify_many, queue_email
    from roles.models import UserRole

    with tenant_context(sub.organization):
        owners = list(UserRole.objects.filter(role__slug="owner").values_list("user_id", flat=True))
        if owners:
            notify_many(recipient_user_ids=owners, title=title, body=body, category="billing", link="/dashboard/billing")
        if sub.organization.email:
            queue_email(to_email=sub.organization.email, subject=title, body=body)
    return 1
