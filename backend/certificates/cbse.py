"""
Statutory CBSE 20-Point Transfer Certificate (TC) helpers and rules.
Enforces compliance with CBSE Examination Bye-Laws Rule 14.1 & Affiliation Bye-Laws.
"""

import datetime
from decimal import Decimal

ORDINAL_DAYS = {
    1: "First", 2: "Second", 3: "Third", 4: "Fourth", 5: "Fifth",
    6: "Sixth", 7: "Seventh", 8: "Eighth", 9: "Ninth", 10: "Tenth",
    11: "Eleventh", 12: "Twelfth", 13: "Thirteenth", 14: "Fourteenth", 15: "Fifteenth",
    16: "Sixteenth", 17: "Seventeenth", 18: "Eighteenth", 19: "Nineteenth", 20: "Twentieth",
    21: "Twenty-First", 22: "Twenty-Second", 23: "Twenty-Third", 24: "Twenty-Fourth", 25: "Twenty-Fifth",
    26: "Twenty-Sixth", 27: "Twenty-Seventh", 28: "Twenty-Eighth", 29: "Twenty-Ninth", 30: "Thirtieth",
    31: "Thirty-First",
}

MONTH_NAMES = [
    "", "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]

ONES = [
    "", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine",
    "Ten", "Eleven", "Twelve", "Thirteen", "Fourteen", "Fifteen", "Sixteen",
    "Seventeen", "Eighteen", "Nineteen"
]
TENS = ["", "", "Twenty", "Thirty", "Forty", "Fifty", "Sixty", "Seventy", "Eighty", "Ninety"]


def _two_digit_words(n: int) -> str:
    if n < 20:
        return ONES[n]
    tens, ones = divmod(n, 10)
    return f"{TENS[tens]} {ONES[ones]}".strip()


def year_to_words(year: int) -> str:
    if 2000 <= year < 2100:
        remainder = year - 2000
        if remainder == 0:
            return "Two Thousand"
        return f"Two Thousand {_two_digit_words(remainder)}"
    elif 1900 <= year < 2000:
        remainder = year - 1900
        return f"Nineteen {_two_digit_words(remainder)}"
    return str(year)


def date_to_words(dt) -> str:
    """Converts a datetime.date or YYYY-MM-DD string into words:
    e.g. 2010-08-15 -> 'Fifteenth August Two Thousand Ten'"""
    if not dt:
        return ""
    if isinstance(dt, str):
        try:
            dt = datetime.date.fromisoformat(dt)
        except ValueError:
            return str(dt)
    day_word = ORDINAL_DAYS.get(dt.day, str(dt.day))
    month_word = MONTH_NAMES[dt.month] if 1 <= dt.month <= 12 else ""
    year_word = year_to_words(dt.year)
    return f"{day_word} {month_word} {year_word}".strip()


def check_student_fee_dues(student):
    """
    Checks StudentFee status for student.
    Returns: (dues_status_text, concession_text)
    """
    try:
        from fees.models import StudentFee
        active_fees = StudentFee.objects.filter(student=student, status="active")
        if not active_fees.exists():
            return "All school dues cleared", ("RTE 25% Quota" if getattr(student, "is_rte", False) else "No")

        total_outstanding = Decimal("0")
        latest_due_date = None
        has_discount = False
        discount_reasons = []

        for fee in active_fees:
            from fees.services import get_outstanding_balance
            bal = get_outstanding_balance(fee)
            if bal > Decimal("0"):
                total_outstanding += bal
                if fee.due_date and (latest_due_date is None or fee.due_date > latest_due_date):
                    latest_due_date = fee.due_date
            if fee.discount_amount > Decimal("0"):
                has_discount = True
                if fee.discount_reason and fee.discount_reason not in discount_reasons:
                    discount_reasons.append(fee.discount_reason)

        if total_outstanding > Decimal("0"):
            month_str = latest_due_date.strftime("%B %Y") if latest_due_date else ""
            dues_text = f"Dues pending: Rs. {total_outstanding:.2f}" + (f" ({month_str})" if month_str else "")
        else:
            latest_fee = active_fees.order_by("-due_date", "-created_at").first()
            if latest_fee and latest_fee.due_date:
                dues_text = latest_fee.due_date.strftime("%B %Y")
            else:
                dues_text = "All school dues cleared"

        if getattr(student, "is_rte", False):
            concession_text = "RTE 25% Quota"
        elif discount_reasons:
            concession_text = ", ".join(discount_reasons)
        elif has_discount:
            concession_text = "Fee concession availed"
        else:
            concession_text = "No"

        return dues_text, concession_text
    except Exception:
        return "All school dues cleared", ("RTE 25% Quota" if getattr(student, "is_rte", False) else "No")

