"""
Importing a school's students, with their parents, from one spreadsheet (see core/bulk_import.py).

One row per student. Parents are matched by mobile number, so brothers and sisters share one parent record,
and a parent already in the school is linked rather than created twice. The class must already exist in the
school ("Class 5", or "Program / Class" when two programs use the same class name); the section is optional.
Students are placed in the current academic year.
"""
import uuid

from django.db import transaction

from core.bulk_import import CheckResult, Column, gender, parse_date, phone, split_name, text

COLUMNS = [
    Column("admission_no", False, "ADM-2026-001", "The school's admission or enrollment number. Left empty, one is made up."),
    Column("first_name", True, "Aarav"),
    Column("middle_name", False, ""),
    Column("last_name", False, "Sharma", "Can be empty for one-word names."),
    Column("gender", True, "Male", "Male, Female or Other (M / F also work)."),
    Column("date_of_birth", True, "15-06-2015", "Day-month-year: 15-06-2015, 15/06/2015, or an Excel date."),
    Column("class", True, "Class 5", "Must match a class in Academics. Use 'Program / Class' if two programs share the name."),
    Column("section", False, "A", "Must match a section of that class, if given."),
    Column("admission_date", False, "01-04-2024"),
    Column("phone", False, "", "The student's own mobile, if any."),
    Column("address", False, "12 MG Road, Pune"),
    Column("father_name", False, "Rajesh Sharma"),
    Column("father_phone", False, "9876543210", "10-digit mobile. Used to link brothers and sisters to the same parent."),
    Column("mother_name", False, "Priya Sharma"),
    Column("mother_phone", False, "9876543211"),
    Column("guardian_name", False, "", "Only when the guardian is not the father or mother."),
    Column("guardian_phone", False, ""),
    Column("guardian_relation", False, "", "e.g. Uncle, Grandmother."),
]

NOTES = [
    "Each student needs at least one parent or guardian with a mobile number, so the school can reach the family.",
    "The first parent given (father, then mother, then guardian) is the primary contact.",
]


def _current_year():
    from academics.models import AcademicYear

    return AcademicYear.objects.filter(is_current=True).first()


def check(rows):
    from academics.models import AcademicLevel, Section
    from families.models import Parent
    from students.models import Student

    result = CheckResult()
    year = _current_year()
    if year is None:
        result.error(1, "", "Set the current academic year first (Academics > Academic years).")
        return result

    levels = list(AcademicLevel.objects.select_related("program"))
    by_name = {}
    for level in levels:
        by_name.setdefault(level.name.strip().lower(), []).append(level)
        by_name.setdefault(f"{level.program.name.strip().lower()} / {level.name.strip().lower()}", []).append(level)
    sections = {(s.level_id, s.name.strip().lower()): s for s in Section.objects.all()}
    taken = set(Student.objects.values_list("enrollment_id", flat=True))
    known_parents = {p.profile.phone: p for p in Parent.objects.select_related("profile") if p.profile.phone}
    seen_numbers = set()

    for raw in rows:
        n = raw["_row"]
        clean = {"_row": n}
        try:
            clean["first_name"] = text(raw.get("first_name"), 50)
            if not clean["first_name"]:
                raise ValueError("is required")
        except ValueError as exc:
            result.error(n, "first_name", f"First name {exc}.")
        for key, limit in (("middle_name", 50), ("last_name", 50), ("address", 500)):
            try:
                clean[key] = text(raw.get(key), limit)
            except ValueError as exc:
                result.error(n, key, f"{key.replace('_', ' ').capitalize()} {exc}.")
        try:
            clean["gender"] = gender(raw.get("gender"))
        except ValueError as exc:
            result.error(n, "gender", f"Gender {exc}.")
        for key, required in (("date_of_birth", True), ("admission_date", False)):
            try:
                clean[key] = parse_date(raw.get(key))
                if required and clean[key] is None:
                    raise ValueError("is required")
            except ValueError as exc:
                result.error(n, key, f"{key.replace('_', ' ').capitalize()} {exc}.")

        number = text(raw.get("admission_no"), 50)
        if number:
            if number in taken:
                result.error(n, "admission_no", f"Admission number {number} is already used in the school.")
            elif number in seen_numbers:
                result.error(n, "admission_no", f"Admission number {number} appears twice in this file.")
            seen_numbers.add(number)
        clean["admission_no"] = number

        class_name = text(raw.get("class")).lower()
        candidates = by_name.get(" / ".join(p.strip() for p in class_name.split("/")) if "/" in class_name else class_name, [])
        if not class_name:
            result.error(n, "class", "Class is required.")
        elif not candidates:
            result.error(n, "class", f"Class '{text(raw.get('class'))}' does not exist. Add it in Academics first.")
        elif len(candidates) > 1:
            result.error(n, "class", f"'{text(raw.get('class'))}' exists in more than one program. Write it as 'Program / Class'.")
        else:
            clean["level"] = candidates[0]
            section_name = text(raw.get("section")).lower()
            clean["section"] = None
            if section_name:
                section = sections.get((candidates[0].id, section_name))
                if section is None:
                    result.error(n, "section", f"Section '{text(raw.get('section'))}' does not exist in {candidates[0].name}.")
                clean["section"] = section

        try:
            clean["phone"] = phone(raw.get("phone"))
        except ValueError as exc:
            result.error(n, "phone", f"Phone {exc}.")

        parents = []
        for prefix, relation in (("father", "father"), ("mother", "mother"), ("guardian", None)):
            name = text(raw.get(f"{prefix}_name"), 150)
            try:
                mobile = phone(raw.get(f"{prefix}_phone"))
            except ValueError as exc:
                result.error(n, f"{prefix}_phone", f"{prefix.capitalize()} phone {exc}.")
                continue
            if not name and not mobile:
                continue
            if not name:
                result.error(n, f"{prefix}_name", f"{prefix.capitalize()} phone is given without a name.")
                continue
            rel = relation or (text(raw.get("guardian_relation")).lower() or "guardian")
            parents.append({"name": name, "phone": mobile, "relation": rel if rel in
                            ("father", "mother", "guardian", "brother", "sister") else "other",
                            "existing": known_parents.get(mobile) if mobile else None})
        if not any(p["phone"] for p in parents):
            result.error(n, "father_phone", "Give at least one parent or guardian with a mobile number.")
        clean["parents"] = parents
        clean["year"] = year
        result.rows.append(clean)
    return result


def preview(row):
    return {
        "row": row["_row"],
        "name": " ".join(p for p in (row.get("first_name"), row.get("middle_name"), row.get("last_name")) if p),
        "class": f"{row['level'].name}{' ' + row['section'].name if row.get('section') else ''}" if row.get("level") else "",
        "admission_no": row.get("admission_no") or "(new)",
        "parents": ", ".join(f"{p['name']} ({p['relation']}{', already in school' if p['existing'] else ''})" for p in row.get("parents", [])),
    }


@transaction.atomic
def save(rows):
    from billing.enforcement import check_student_capacity
    from families.models import Parent, StudentParentRelation
    from profiles.models import Profile
    from students.models import Student, StudentLevel

    check_student_capacity(adding=len(rows))
    new_parents = {}  # phone -> Parent created in this import (brothers and sisters in the same file)
    created = 0
    for row in rows:
        profile = Profile.objects.create(
            first_name=row["first_name"], middle_name=row.get("middle_name", ""), last_name=row.get("last_name", ""),
            gender=row["gender"], date_of_birth=row["date_of_birth"], phone=row.get("phone", ""),
            address=row.get("address", ""),
        )
        student = Student.objects.create(
            profile=profile, enrollment_id=row["admission_no"] or f"STD-{uuid.uuid4().hex[:8].upper()}",
            admission_date=row.get("admission_date"),
        )
        StudentLevel.objects.create(student=student, level=row["level"], section=row.get("section"),
                                    academic_year=row["year"].name, academic_year_ref=row["year"], is_current=True)
        for index, info in enumerate(row["parents"]):
            parent = info["existing"] or (new_parents.get(info["phone"]) if info["phone"] else None)
            if parent is None:
                first, middle, last = split_name(info["name"])
                parent = Parent.objects.create(profile=Profile.objects.create(
                    first_name=first, middle_name=middle, last_name=last, phone=info["phone"],
                    gender={"father": "male", "mother": "female"}.get(info["relation"], "other"),
                    address=row.get("address", "")))
                if info["phone"]:
                    new_parents[info["phone"]] = parent
            StudentParentRelation.objects.get_or_create(
                student=student, parent=parent,
                defaults={"relation_type": info["relation"], "is_primary_contact": index == 0})
        created += 1
    return created
