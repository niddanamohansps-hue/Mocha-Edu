"""
Importing fees that students still owe when the school starts using EduSekai (see core/bulk_import.py).

One row per student and fee. The student is found by admission number; the fee head must already exist
(Fees > Fee Structures). Each row becomes an ordinary fee the student owes, so it can be paid at the counter
or online like any other.
"""
from django.db import transaction

from core.bulk_import import CheckResult, Column, amount, parse_date, text

COLUMNS = [
    Column("admission_no", True, "ADM-2026-001", "The student's admission number in EduSekai."),
    Column("fee_head", True, "Tuition", "Must match a fee head in Fees (e.g. Tuition, Transport)."),
    Column("amount_due", True, "12500", "What is still owed, in rupees."),
    Column("due_date", False, "30-04-2026"),
    Column("academic_year", False, "2026-27", "Empty = the current academic year."),
]


def check(rows):
    from academics.models import AcademicYear
    from fees.models import FeeHead
    from students.models import Student

    result = CheckResult()
    students = {s.enrollment_id.strip().lower(): s for s in Student.objects.select_related("profile")}
    heads = {h.name.strip().lower(): h for h in FeeHead.objects.filter(is_active=True)}
    years = {y.name: y for y in AcademicYear.objects.all()}
    current = next((y for y in years.values() if y.is_current), None)
    seen = set()
    for raw in rows:
        n = raw["_row"]
        clean = {"_row": n}
        number = text(raw.get("admission_no"), 50)
        clean["student"] = students.get(number.lower())
        if not number:
            result.error(n, "admission_no", "Admission number is required.")
        elif clean["student"] is None:
            result.error(n, "admission_no", f"No student with admission number {number}. Import the students first.")
        head_name = text(raw.get("fee_head"), 100)
        clean["fee_head"] = heads.get(head_name.lower())
        if not head_name:
            result.error(n, "fee_head", "Fee head is required.")
        elif clean["fee_head"] is None:
            result.error(n, "fee_head", f"Fee head '{head_name}' does not exist. Add it in Fees first.")
        try:
            clean["amount_due"] = amount(raw.get("amount_due"))
        except ValueError as exc:
            result.error(n, "amount_due", f"Amount {exc}.")
        try:
            clean["due_date"] = parse_date(raw.get("due_date"))
        except ValueError as exc:
            result.error(n, "due_date", f"Due date {exc}.")
        year_name = text(raw.get("academic_year"), 20)
        year = years.get(year_name) if year_name else current
        if year is None:
            result.error(n, "academic_year", f"Academic year '{year_name}' does not exist." if year_name
                         else "Set the current academic year first.")
        clean["academic_year"] = year.name if year else ""
        key = (number.lower(), head_name.lower(), clean["academic_year"])
        if all(key) and key in seen:
            result.error(n, "fee_head", "The same student, fee and year appear twice in this file.")
        seen.add(key)
        result.rows.append(clean)
    return result


def preview(row):
    student = row.get("student")
    return {
        "row": row["_row"],
        "admission_no": student.enrollment_id if student else "",
        "student": str(student.profile).strip() if student else "",
        "fee": row["fee_head"].name if row.get("fee_head") else "",
        "amount_due": str(row.get("amount_due", "")),
        "academic_year": row.get("academic_year", ""),
    }


@transaction.atomic
def save(rows):
    from fees.services import assign_student_fee

    for row in rows:
        assign_student_fee(student=row["student"], fee_head=row["fee_head"], academic_year=row["academic_year"],
                           amount_due=row["amount_due"], due_date=row.get("due_date"))
    return len(rows)
