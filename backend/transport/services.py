"""Transport rules: seats and capacity, moving a student, and the monthly transport billing run.

A route is one bus run, so capacity is counted per route: on no day may more students hold a seat on the
route than its vehicle has seats. A seat counts from its start date to its end date, so a seat that ends next
month still counts until then, and one that starts next month counts from then. Stops are optional: a route with stops needs a stop on every seat, a route without
stops takes none. A seat's fee is its stop's own fee when the stop has one, otherwise the route's fee. Every change that touches seats locks the route row first, so two people cannot
both take the last seat. Billing writes ordinary ``fees.StudentFee`` rows (head "Transport") and records
each one in ``TransportBill``; the unique (student, month) rule on that table is what stops a repeated
run, or two people running at once, from billing anyone twice.
"""
from calendar import monthrange
from datetime import date, timedelta

from django.db import IntegrityError, transaction
from rest_framework import serializers

from core.dates import school_today
from fees.models import FeeHead
from fees.services import assign_student_fee
from students.models import Student

from .models import Driver, Route, StudentTransport, TransportBill, Vehicle

FEE_HEAD_NAME = "Transport"
MIN_YEAR, MAX_YEAR = 2000, 2100


def seats_taken(route, *, on=None, excluding_student=None):
    """The most students holding a seat on ``route`` on any day from ``on`` (default today) onward.

    Occupancy only rises on a day a seat starts, so the peak is found by checking ``on`` and every later start date.
    """
    on = on or school_today()
    seats = StudentTransport.objects.filter(route=route).exclude(end_date__lt=on)
    if excluding_student is not None:
        seats = seats.exclude(student=excluding_student)
    spans = list(seats.values_list("start_date", "end_date"))
    days = {on} | {start for start, _ in spans if start > on}
    return max(
        (sum(1 for start, end in spans if start <= day and (end is None or end >= day)) for day in days),
        default=0,
    )


def check_capacity(route, vehicle, *, taken):
    """Raise unless ``taken`` students fit in ``vehicle`` (a route with no vehicle has no limit yet)."""
    if vehicle is not None and taken >= vehicle.capacity:
        raise serializers.ValidationError(
            {"route": f"The bus on this route ({vehicle.registration_number}) is full: {vehicle.capacity} of {vehicle.capacity} seats are taken."}
        )


# --- Seats -------------------------------------------------------------------------------------------------

@transaction.atomic
def assign_student(*, student, route, stop=None, start_date, mode=StudentTransport.Mode.BOTH, pickup_note="", user_id=None):
    """Give ``student`` a seat on ``route`` (at ``stop`` when the route has stops) from ``start_date``. A
    student who already has a seat is moved: the old seat ends the day before the new one starts, so there
    is no gap and no overlap."""
    # Lock only the route row: the vehicle is an optional join and PostgreSQL cannot lock the nullable side.
    route = Route.objects.select_for_update(of=("self",)).select_related("vehicle").get(pk=route.pk)
    student = Student.objects.select_for_update().get(pk=student.pk)
    if student.status != "active":
        raise serializers.ValidationError({"student": "Only an active student can have a transport seat."})
    if not route.is_active:
        raise serializers.ValidationError({"route": "This route is switched off."})
    if route.vehicle_id is None:
        raise serializers.ValidationError({"route": "This route has no vehicle yet, so it has no seats."})
    if not route.vehicle.is_active:
        raise serializers.ValidationError({"route": "The bus on this route is switched off."})

    has_stops = route.stops.exists()
    if has_stops and stop is None:
        raise serializers.ValidationError({"stop": "This route has stops. Choose where the student gets on."})
    if stop is not None and stop.route_id != route.id:
        raise serializers.ValidationError({"stop": "That stop is not on this route."})
    if not has_stops and stop is not None:
        raise serializers.ValidationError({"stop": "This route has no stops."})
    pickup_note = (pickup_note or "").strip()
    if len(pickup_note) > 255:
        raise serializers.ValidationError({"pickup_note": "Keep the note under 255 characters."})

    current = StudentTransport.objects.filter(student=student, end_date__isnull=True).first()
    if current is not None:
        same = (
            current.route_id == route.id and current.stop_id == (stop.id if stop else None)
            and current.mode == mode and current.pickup_note == pickup_note
        )
        if same:
            raise serializers.ValidationError({"route": "This student already has exactly this seat."})
        if start_date <= current.start_date:
            raise serializers.ValidationError(
                {"start_date": f"The current seat started on {current.start_date:%d %b %Y}. Choose a later date to move the student."}
            )
    taken = seats_taken(route, on=start_date, excluding_student=student)
    check_capacity(route, route.vehicle, taken=taken)

    if current is not None:
        current.end_date = start_date - timedelta(days=1)
        current.save(update_fields=["end_date", "updated_at"])
    return StudentTransport.objects.create(
        student=student, route=route, stop=stop, mode=mode, pickup_note=pickup_note,
        start_date=start_date, created_by_user_id=user_id,
    )


def end_assignment(*, assignment, end_date):
    with transaction.atomic():
        assignment = StudentTransport.objects.select_for_update().get(pk=assignment.pk)
        if assignment.end_date is not None:
            raise serializers.ValidationError({"end_date": "This seat has already ended."})
        if end_date < assignment.start_date:
            raise serializers.ValidationError({"end_date": "A seat cannot end before it starts."})
        assignment.end_date = end_date
        assignment.save(update_fields=["end_date", "updated_at"])
        return assignment


# --- Monthly billing -----------------------------------------------------------------------------------------

def month_bounds(year, month):
    if not (MIN_YEAR <= year <= MAX_YEAR) or not 1 <= month <= 12:
        raise serializers.ValidationError({"month": "Choose a real year and month."})
    return date(year, month, 1), date(year, month, monthrange(year, month)[1])


def _academic_year(student):
    current = student.enrollments.filter(is_current=True).first()
    return current.academic_year if current else ""


def bill_month(*, year, month, due_date=None, user_id=None):
    """Create one Transport fee for every student with a paid seat in the month. A student is billed the
    full stop fee if their seat covers any day of the month; a student who moved during the month is billed
    for the seat they moved to. Safe to repeat: students already billed for the month are left alone.
    Returns a summary of what happened."""
    first, last = month_bounds(year, month)
    if first > school_today():
        raise serializers.ValidationError({"month": "Transport cannot be billed for a month that has not started."})
    if due_date is not None and due_date < first:
        raise serializers.ValidationError({"due_date": "The due date cannot be before the month being billed."})
    due_date = due_date or last

    head, _ = FeeHead.objects.get_or_create(name=FEE_HEAD_NAME)
    if not head.is_active:
        raise serializers.ValidationError({"month": "The Transport fee head is switched off in Fees. Switch it on first."})

    seats = (
        StudentTransport.objects.filter(start_date__lte=last, student__status="active")
        .exclude(end_date__lt=first)
        .select_related("route", "stop", "student__profile")
        .order_by("student_id", "-start_date")
    )
    latest = {}
    for seat in seats:
        latest.setdefault(seat.student_id, seat)

    # A bill whose fee was later cancelled in Fees does not count: the student can be billed for the month again.
    bills = {b.student_id: b for b in TransportBill.objects.filter(month=first).select_related("student_fee")}
    already = {sid for sid, b in bills.items() if b.student_fee.status != "cancelled"}
    summary = {
        "month": first.isoformat(), "billed": 0, "total": "0.00", "already_billed": 0,
        "no_fee": 0, "no_enrollment": [],
    }
    total = 0
    for student_id, seat in latest.items():
        if student_id in already:
            summary["already_billed"] += 1
            continue
        if seat.fee <= 0:
            summary["no_fee"] += 1
            continue
        year_label = _academic_year(seat.student)
        if not year_label:
            profile = seat.student.profile
            summary["no_enrollment"].append(f"{profile.first_name} {profile.last_name}".strip())
            continue
        try:
            with transaction.atomic():
                previous = bills.get(student_id)
                if previous is not None:
                    # Re-billing after the first fee was cancelled: lock that bill so two runs cannot both re-bill.
                    previous = TransportBill.objects.select_for_update().select_related("student_fee").get(pk=previous.pk)
                    if previous.student_fee.status != "cancelled":
                        raise IntegrityError("billed again by another run")
                fee = assign_student_fee(
                    student=seat.student, fee_head=head, academic_year=year_label,
                    amount_due=seat.fee, due_date=due_date,
                )
                if previous is not None:
                    # The cancelled fee stays in Fees with its reason; the bill now points at the new one.
                    previous.route, previous.stop, previous.amount = seat.route, seat.stop, seat.fee
                    previous.student_fee, previous.billed_by_user_id = fee, user_id
                    previous.save(update_fields=["route", "stop", "amount", "student_fee", "billed_by_user_id"])
                else:
                    TransportBill.objects.create(
                        student=seat.student, month=first, route=seat.route, stop=seat.stop, amount=seat.fee,
                        student_fee=fee, billed_by_user_id=user_id,
                    )
        except IntegrityError:
            summary["already_billed"] += 1  # another run billed this student a moment ago
            continue
        summary["billed"] += 1
        total += seat.fee
    summary["total"] = f"{total:.2f}"
    return summary


# --- Expiring documents --------------------------------------------------------------------------------------

def expiring_documents(*, days=30, today=None):
    """Insurance, fitness and licence dates that are past or fall within ``days`` days, soonest first."""
    today = today or school_today()
    horizon = today + timedelta(days=days)
    rows = []
    for vehicle in Vehicle.objects.filter(is_active=True):
        for label, expiry in (("Insurance", vehicle.insurance_expiry), ("Fitness certificate", vehicle.fitness_expiry)):
            if expiry and expiry <= horizon:
                rows.append({"kind": "vehicle", "id": str(vehicle.id), "subject": vehicle.registration_number,
                             "document": label, "expiry": expiry.isoformat(), "days_left": (expiry - today).days})
    for driver in Driver.objects.filter(is_active=True, license_expiry__isnull=False, license_expiry__lte=horizon):
        rows.append({"kind": "driver", "id": str(driver.id), "subject": driver.full_name,
                     "document": "Licence", "expiry": driver.license_expiry.isoformat(),
                     "days_left": (driver.license_expiry - today).days})
    return sorted(rows, key=lambda r: (r["expiry"], r["subject"]))
