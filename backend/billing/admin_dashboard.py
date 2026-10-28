"""
The platform owner's billing dashboard, inside Django admin (superusers only):
/admin/billing/dashboard/

Figures: schools by status, monthly recurring revenue (MRR, before GST), revenue this month and this
financial year, an overdue list, every school with its plan, paid-until date and student usage, and the
latest payments. Actions (POST, CSRF-protected, audited in the admin log): extend a trial, move a school to
another plan or cycle, and mark a school as legacy (full access, never billed).
"""
from datetime import timedelta
from decimal import Decimal

from django.contrib import admin, messages
from django.contrib.admin.models import CHANGE, LogEntry
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import PermissionDenied
from django.db.models import Sum
from django.shortcuts import redirect
from django.template.response import TemplateResponse
from django.utils import timezone
from django_tenants.utils import tenant_context

from .models import CYCLE_CHOICES, MONTHLY, YEARLY, Invoice, Plan, Subscription
from .services import financial_year, refresh_status

ZERO = Decimal("0.00")


def monthly_value(sub):
    """What the subscription is worth per month before GST (one-time, trial and legacy count as 0)."""
    if sub.is_legacy or sub.status not in (Subscription.ACTIVE, Subscription.PAST_DUE):
        return ZERO
    if sub.cycle == MONTHLY and sub.plan.monthly_price:
        return sub.plan.monthly_price
    if sub.cycle == YEARLY and sub.plan.yearly_price:
        return (sub.plan.yearly_price / 12).quantize(Decimal("0.01"))
    return ZERO


def _students(organization):
    from students.models import Student

    try:
        with tenant_context(organization):
            return Student.objects.filter(status="active").count()
    except Exception:  # noqa: BLE001 - a broken school schema must not break the dashboard
        return None


def summary(now=None):
    now = now or timezone.now()
    subs = list(Subscription.objects.select_related("plan", "organization").order_by("organization__name"))
    for sub in subs:
        refresh_status(sub, now=now)

    counts = {key: 0 for key, _ in Subscription.STATUS_CHOICES}
    counts["legacy"] = 0
    rows = []
    for sub in subs:
        counts["legacy" if sub.is_legacy else sub.status] += 1
        students = _students(sub.organization)
        limit = sub.plan.student_limit
        rows.append({
            "sub": sub,
            "students": students,
            "limit": limit,
            "over_limit": bool(limit and students is not None and students > limit),
            "mrr": monthly_value(sub),
            "days_overdue": (now - sub.paid_until).days if sub.paid_until and sub.paid_until < now and not sub.is_legacy else 0,
        })

    paid = Invoice.objects.filter(status=Invoice.PAID)
    month_start = timezone.localtime(now).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    fy = financial_year(now)
    fy_start = timezone.make_aware(timezone.datetime(int(fy[:4]), 4, 1))

    def total(queryset):
        values = queryset.aggregate(t=Sum("total"), a=Sum("amount"))
        return values["t"] or ZERO, values["a"] or ZERO

    return {
        "counts": counts,
        "school_count": len(subs),
        "mrr": sum((r["mrr"] for r in rows), ZERO),
        "month": total(paid.filter(paid_at__gte=month_start)),
        "year": total(paid.filter(paid_at__gte=fy_start)),
        "financial_year": fy,
        "rows": rows,
        "overdue": [r for r in rows if r["sub"].status in (Subscription.PAST_DUE, Subscription.READ_ONLY)],
        "trials_ending": [r for r in rows if r["sub"].status == Subscription.TRIAL and r["sub"].trial_ends_at
                          and r["sub"].trial_ends_at <= now + timedelta(days=7)],
        "recent_payments": list(paid.select_related("subscription__organization").order_by("-paid_at")[:15]),
    }


def _log(request, sub, message):
    LogEntry.objects.log_action(
        user_id=request.user.pk, content_type_id=ContentType.objects.get_for_model(Subscription).pk,
        object_id=str(sub.pk), object_repr=str(sub)[:200], action_flag=CHANGE, change_message=message,
    )


def _act(request):
    sub = Subscription.objects.select_related("plan", "organization").filter(pk=request.POST.get("subscription")).first()
    if sub is None:
        messages.error(request, "School not found.")
        return
    action = request.POST.get("action")
    name = sub.organization.name
    if action == "extend_trial":
        try:
            days = int(request.POST.get("days", "0"))
        except ValueError:
            days = 0
        if not 1 <= days <= 90:
            messages.error(request, "Extend a trial by 1 to 90 days.")
            return
        base = max(timezone.now(), sub.trial_ends_at or timezone.now())
        sub.trial_ends_at = base + timedelta(days=days)
        sub.status, sub.grace_ends_at = Subscription.TRIAL, None
        sub.save(update_fields=["trial_ends_at", "status", "grace_ends_at", "updated_at"])
        _log(request, sub, f"Trial extended by {days} days to {sub.trial_ends_at:%d %b %Y}.")
        messages.success(request, f"{name}: trial extended by {days} days.")
    elif action == "change_plan":
        plan = Plan.objects.filter(pk=request.POST.get("plan")).first()
        cycle = request.POST.get("cycle")
        if plan is None or not plan.offers(cycle):
            messages.error(request, "That plan is not offered on that cycle.")
            return
        old = f"{sub.plan.name} ({sub.cycle})"
        sub.plan, sub.cycle, sub.is_legacy = plan, cycle, False
        sub.save(update_fields=["plan", "cycle", "is_legacy", "updated_at"])
        _log(request, sub, f"Plan changed from {old} to {plan.name} ({cycle}). Takes effect from the next payment.")
        messages.success(request, f"{name}: moved to {plan.name} ({cycle}). The new price applies from the next payment.")
    elif action == "mark_legacy":
        sub.is_legacy, sub.status, sub.grace_ends_at = True, Subscription.ACTIVE, None
        sub.save(update_fields=["is_legacy", "status", "grace_ends_at", "updated_at"])
        _log(request, sub, "Marked legacy: full access, not billed.")
        messages.success(request, f"{name}: full access, not billed.")
    else:
        messages.error(request, "Unknown action.")


@staff_member_required
def billing_dashboard(request):
    if not request.user.is_superuser:
        raise PermissionDenied
    if request.method == "POST":
        _act(request)
        return redirect(request.path)
    context = {
        **admin.site.each_context(request),
        "title": "Billing dashboard",
        "plans": Plan.objects.all(),
        "cycles": CYCLE_CHOICES,
        **summary(),
    }
    return TemplateResponse(request, "admin/billing/dashboard.html", context)
