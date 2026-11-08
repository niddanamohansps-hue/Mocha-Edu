"""Calls about unpaid fees and promises to pay.

A promise is *kept* once the student has paid at least the promised amount (or anything, if no amount was given)
since the call; *pending* until its date; *broken* once the date has passed without that payment. Only the most
recent call that carries a promise counts as the student's promise."""
from datetime import timedelta
from decimal import Decimal, InvalidOperation

from django.db.models import Sum
from rest_framework.exceptions import ValidationError

from core.audit import log_action
from core.dates import school_today

from .models import FeeCallNote, PaymentAllocation, StudentFee
from .services import annotate_with_outstanding_balance

MAX_PROMISE_DAYS = 90


def _paid_since(student_id, moment):
    """Net money paid for this student after ``moment`` (reversals are negative allocations)."""
    total = PaymentAllocation.objects.filter(student_fee__student_id=student_id, created_at__gte=moment).aggregate(t=Sum("amount"))["t"]
    return total or Decimal("0")


def promise_state(note, today=None):
    """``None`` for a call with no promise, else ``{"amount", "date", "status"}``."""
    if note.promise_date is None:
        return None
    today = today or school_today()
    paid = _paid_since(note.student_id, note.created_at)
    needed = note.promise_amount if note.promise_amount else Decimal("0.01")
    if paid >= needed:
        status = "kept"
    elif note.promise_date >= today:
        status = "pending"
    else:
        status = "broken"
    return {"amount": note.promise_amount, "date": note.promise_date, "status": status, "paid_since": paid}


def outstanding_of(student_id):
    fees = annotate_with_outstanding_balance(StudentFee.objects.filter(student_id=student_id, status="active"))
    return sum((amount for amount in fees.filter(_outstanding__gt=0).values_list("_outstanding", flat=True)), Decimal("0"))


def record_call(student, *, outcome, note, promise_amount, promise_date, user, request=None):
    """Write down a call. A promise needs the 'promised' outcome and a date within the next 90 days; the student must
    actually owe something."""
    if outcome not in FeeCallNote.Outcome.values:
        raise ValidationError({"outcome": ["Choose what happened on the call."]})
    note = " ".join((note or "").split())
    if not note:
        raise ValidationError({"note": ["Write a short note of what was said."]})
    if len(note) > 500:
        raise ValidationError({"note": ["Keep the note under 500 characters."]})
    owed = outstanding_of(student.pk)
    if owed <= 0:
        raise ValidationError({"non_field_errors": ["This student has nothing outstanding."]})

    amount = None
    if outcome == FeeCallNote.Outcome.PROMISED:
        today = school_today()
        if promise_date is None:
            raise ValidationError({"promise_date": ["Give the date they promised to pay by."]})
        if promise_date < today:
            raise ValidationError({"promise_date": ["The promised date cannot be in the past."]})
        if promise_date > today + timedelta(days=MAX_PROMISE_DAYS):
            raise ValidationError({"promise_date": [f"A promise can be at most {MAX_PROMISE_DAYS} days away."]})
        if promise_amount not in (None, ""):
            try:
                amount = Decimal(str(promise_amount)).quantize(Decimal("0.01"))
            except (InvalidOperation, ValueError):
                raise ValidationError({"promise_amount": ["Enter the amount as a number."]})
            if not amount.is_finite() or amount <= 0:
                raise ValidationError({"promise_amount": ["The promised amount must be above zero."]})
            if amount > owed:
                raise ValidationError({"promise_amount": [f"That is more than the {owed} outstanding."]})
    else:
        promise_date = None

    call = FeeCallNote.objects.create(
        student=student, outcome=outcome, note=note, promise_amount=amount, promise_date=promise_date,
        created_by_user_id=getattr(user, "id", None),
        created_by_name=user.get_username() if getattr(user, "is_authenticated", False) else "",
    )
    log_action(request, action="CREATE", model_name="FeeCallNote", object_id=call.id,
               changes={"student": str(student.id), "outcome": outcome, "promise_date": promise_date.isoformat() if promise_date else None})
    return call


def history(student_id, today=None):
    """Every call for a student, newest first, with the state of any promise."""
    today = today or school_today()
    latest_promise = FeeCallNote.objects.filter(student_id=student_id, promise_date__isnull=False).order_by("-created_at").first()
    rows = []
    for call in FeeCallNote.objects.filter(student_id=student_id):
        state = promise_state(call, today) if call.promise_date else None
        if state is not None and latest_promise is not None and call.pk != latest_promise.pk and state["status"] == "pending":
            state["status"] = "replaced"  # a newer promise took over before this one's date
        rows.append({
            "id": call.id, "outcome": call.outcome, "outcome_label": call.get_outcome_display(), "note": call.note,
            "promise": state, "by": call.created_by_name, "at": call.created_at,
        })
    return rows


def latest_for(student_ids, today=None):
    """``{student_id: {"last_call_at", "last_outcome", "promise"}}`` for the dues list, in two queries plus one
    payment sum per student that has a live promise."""
    today = today or school_today()
    out = {}
    notes = FeeCallNote.objects.filter(student_id__in=student_ids).order_by("student_id", "-created_at")
    promised = set()
    for call in notes:
        entry = out.setdefault(call.student_id, {"last_call_at": call.created_at, "last_outcome": call.outcome, "promise": None})
        if entry["promise"] is None and call.student_id not in promised and call.promise_date is not None:
            promised.add(call.student_id)
            entry["promise"] = promise_state(call, today)
    return out
