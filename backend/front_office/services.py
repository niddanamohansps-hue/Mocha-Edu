from datetime import date
from django.utils import timezone
from .models import VisitorLog, StudentGatePass, PostalRecord


def generate_visitor_pass_number(target_date=None):
    year = (target_date or timezone.now().date()).year
    prefix = f"VIS-{year}-"
    last = (
        VisitorLog.objects.filter(pass_number__startswith=prefix)
        .order_by("-pass_number")
        .values_list("pass_number", flat=True)
        .first()
    )
    if not last:
        seq = 1
    else:
        try:
            seq = int(last.split("-")[-1]) + 1
        except (ValueError, IndexError):
            seq = 1
    return f"{prefix}{seq:04d}"


def generate_gate_pass_number(target_date=None):
    year = (target_date or timezone.now().date()).year
    prefix = f"GP-{year}-"
    last = (
        StudentGatePass.objects.filter(pass_number__startswith=prefix)
        .order_by("-pass_number")
        .values_list("pass_number", flat=True)
        .first()
    )
    if not last:
        seq = 1
    else:
        try:
            seq = int(last.split("-")[-1]) + 1
        except (ValueError, IndexError):
            seq = 1
    return f"{prefix}{seq:04d}"


def get_front_office_overview():
    today = timezone.localdate()
    active_visitors = VisitorLog.objects.filter(status=VisitorLog.Status.ACTIVE).count()
    visitors_today = VisitorLog.objects.filter(check_in_time__date=today).count()
    gate_passes_today = StudentGatePass.objects.filter(departure_date=today).count()
    active_gate_passes = StudentGatePass.objects.filter(
        departure_date=today, status=StudentGatePass.Status.ISSUED
    ).count()
    postal_inward_month = PostalRecord.objects.filter(
        record_type=PostalRecord.RecordType.INWARD,
        dispatch_date__year=today.year,
        dispatch_date__month=today.month,
    ).count()

    return {
        "today": today.isoformat(),
        "active_visitors_inside": active_visitors,
        "visitors_today": visitors_today,
        "gate_passes_today": gate_passes_today,
        "active_gate_passes": active_gate_passes,
        "postal_inward_this_month": postal_inward_month,
    }

