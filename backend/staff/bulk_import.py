"""Importing a school's staff from one spreadsheet (see core/bulk_import.py). One row per staff member."""
from django.db import transaction

from core.bulk_import import CheckResult, Column, gender, parse_date, phone, text, yes_no

COLUMNS = [
    Column("employee_id", True, "EMP-001", "Must be unique in the school."),
    Column("first_name", True, "Sunita"),
    Column("middle_name", False, ""),
    Column("last_name", False, "Rao"),
    Column("gender", False, "Female", "Male, Female or Other."),
    Column("date_of_birth", False, "02-11-1985"),
    Column("phone", False, "9812345678", "10-digit mobile."),
    Column("email", False, "sunita.rao@example.com"),
    Column("designation", True, "Teacher", "e.g. Teacher, Accountant, Clerk, Driver."),
    Column("department", False, "Science"),
    Column("joining_date", False, "01-06-2019"),
    Column("qualification", False, "M.Sc, B.Ed"),
    Column("experience_years", False, "8"),
    Column("is_teacher", False, "Yes", "Yes for teaching staff (they can then be given classes and subjects)."),
    Column("subject_specialization", False, "Mathematics", "For teachers."),
    Column("address", False, ""),
]


def check(rows):
    from django.core.validators import validate_email

    from staff.models import StaffMember

    result = CheckResult()
    taken = set(StaffMember.objects.values_list("employee_id", flat=True))
    seen = set()
    for raw in rows:
        n = raw["_row"]
        clean = {"_row": n}
        employee_id = text(raw.get("employee_id"), 50)
        if not employee_id:
            result.error(n, "employee_id", "Employee ID is required.")
        elif employee_id in taken:
            result.error(n, "employee_id", f"Employee ID {employee_id} is already used in the school.")
        elif employee_id in seen:
            result.error(n, "employee_id", f"Employee ID {employee_id} appears twice in this file.")
        seen.add(employee_id)
        clean["employee_id"] = employee_id
        for key, limit, required in (("first_name", 50, True), ("middle_name", 50, False), ("last_name", 50, False),
                                     ("designation", 100, True), ("department", 100, False),
                                     ("qualification", 500, False), ("address", 500, False),
                                     ("subject_specialization", 100, False)):
            try:
                clean[key] = text(raw.get(key), limit)
                if required and not clean[key]:
                    raise ValueError("is required")
            except ValueError as exc:
                result.error(n, key, f"{key.replace('_', ' ').capitalize()} {exc}.")
        try:
            clean["gender"] = gender(raw.get("gender")) if text(raw.get("gender")) else "other"
        except ValueError as exc:
            result.error(n, "gender", f"Gender {exc}.")
        for key in ("date_of_birth", "joining_date"):
            try:
                clean[key] = parse_date(raw.get(key))
            except ValueError as exc:
                result.error(n, key, f"{key.replace('_', ' ').capitalize()} {exc}.")
        try:
            clean["phone"] = phone(raw.get("phone"))
        except ValueError as exc:
            result.error(n, "phone", f"Phone {exc}.")
        email = text(raw.get("email"), 254)
        if email:
            try:
                validate_email(email)
            except Exception:  # noqa: BLE001
                result.error(n, "email", f"'{email}' is not a valid email address.")
        clean["email"] = email
        years = text(raw.get("experience_years")) or "0"
        if not years.isdigit() or int(years) > 60:
            result.error(n, "experience_years", "Experience should be a whole number of years.")
            years = "0"
        clean["experience_years"] = int(years)
        clean["is_teacher"] = yes_no(raw.get("is_teacher"))
        result.rows.append(clean)
    return result


def preview(row):
    return {
        "row": row["_row"],
        "employee_id": row.get("employee_id"),
        "name": " ".join(p for p in (row.get("first_name"), row.get("middle_name"), row.get("last_name")) if p),
        "designation": row.get("designation"),
        "teacher": "Yes" if row.get("is_teacher") else "No",
    }


@transaction.atomic
def save(rows):
    from profiles.models import Profile
    from staff.models import Instructor, StaffMember

    for row in rows:
        profile = Profile.objects.create(
            first_name=row["first_name"], middle_name=row.get("middle_name", ""), last_name=row.get("last_name", ""),
            gender=row["gender"], date_of_birth=row.get("date_of_birth"), phone=row.get("phone", ""),
            email=row.get("email") or None, address=row.get("address", ""),
        )
        staff = StaffMember.objects.create(
            profile=profile, employee_id=row["employee_id"], designation=row["designation"],
            department=row.get("department", ""), joining_date=row.get("joining_date"),
            qualification=row.get("qualification", ""), experience_years=row.get("experience_years", 0),
        )
        if row.get("is_teacher"):
            Instructor.objects.create(staff_member=staff, specialization=row.get("subject_specialization", "") or "General")
    return len(rows)
