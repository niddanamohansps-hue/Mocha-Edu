"""How much was billed, how much of it has been collected, and how much is still owed, by month and by class.

*Billed* is what fell due in the period, after discounts. *Collected* is what has been paid against exactly those
fees so far, so a month's collection rate can never pass 100 per cent and an old month keeps improving as late
payers settle. *Received in the month* is the other question: the cash that came in during that month, whichever
month it was for. The two are shown side by side and never mixed.

The money is the same arithmetic as the outstanding report (amount due less discount less net allocations), so
these figures cannot disagree with it.
"""
from collections import defaultdict
from decimal import Decimal

from django.db.models import Sum
from django.db.models.functions import TruncMonth

from core.dates import school_zone

from .models import PaymentAllocation, StudentFee
from .services import annotate_with_allocation_total

ZERO = Decimal("0")
MAX_FEES = 200000  # a bound on what one request reads, far beyond a school's real number of fees


def _rate(collected, billed):
    return None if billed <= 0 else round(float(collected / billed) * 100, 1)


def _line(billed, collected):
    return {"billed": billed, "collected": collected, "outstanding": billed - collected, "rate": _rate(collected, billed)}


def collection_summary(academic_year, month=None):
    """``{"by_month", "by_class", "totals", "month"}`` for one academic year. ``by_class`` covers the chosen month
    (``"YYYY-MM"``), or the whole year when none is chosen."""
    fees = annotate_with_allocation_total(StudentFee.objects.filter(status="active", academic_year=academic_year))
    rows = list(fees.values_list("due_date", "amount_due", "discount_amount", "_allocations_total", "level_name")[:MAX_FEES])

    by_month = defaultdict(lambda: [ZERO, ZERO])
    by_class = defaultdict(lambda: [ZERO, ZERO])
    total = [ZERO, ZERO]
    for due, amount, discount, paid, level in rows:
        billed = amount - discount
        key = due.strftime("%Y-%m") if due else "undated"
        by_month[key][0] += billed
        by_month[key][1] += paid
        total[0] += billed
        total[1] += paid
        if month is None or key == month:
            by_class[level or "Not recorded"][0] += billed
            by_class[level or "Not recorded"][1] += paid

    received = {}
    cash = (
        PaymentAllocation.objects.filter(student_fee__academic_year=academic_year, student_fee__status="active")
        .annotate(month=TruncMonth("created_at", tzinfo=school_zone()))
        .values("month")
        .annotate(total=Sum("amount"))
    )
    for row in cash:
        received[row["month"].strftime("%Y-%m")] = row["total"] or ZERO

    months = sorted(set(by_month) | set(received), key=lambda k: (k == "undated", k))
    return {
        "academic_year": academic_year,
        "month": month,
        "totals": {**_line(*total), "fees": len(rows), "capped": len(rows) >= MAX_FEES},
        "by_month": [
            {"month": key, **_line(*by_month.get(key, [ZERO, ZERO])), "received": received.get(key, ZERO)} for key in months
        ],
        "by_class": [
            {"level": name, **_line(*vals)} for name, vals in sorted(by_class.items(), key=lambda kv: kv[0].lower())
        ],
    }
