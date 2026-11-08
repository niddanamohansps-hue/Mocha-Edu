"""Who owes what, and for how long: the fee dues of every student in one row, aged by how late the oldest fee is.

The money comes from ``annotate_with_outstanding_balance``, the same arithmetic the outstanding report and the
reminders use, so the figures here can never disagree with them.
"""
from collections import defaultdict
from decimal import Decimal

from core.dates import school_today

from .models import StudentFee
from .services import annotate_with_outstanding_balance

BANDS = ("current", "1-30", "31-60", "61-90", "90+")
SORTS = ("amount", "age", "name")
MAX_FEES = 50000  # a safety bound on what one request reads; far beyond a school's real count of open fees


def band_for(days_late):
    """The ageing band for a fee that is ``days_late`` days past its due date (0 or less means not yet due)."""
    if days_late <= 0:
        return "current"
    if days_late <= 30:
        return "1-30"
    if days_late <= 60:
        return "31-60"
    if days_late <= 90:
        return "61-90"
    return "90+"


def _guardians(student_ids):
    """``{student_id: (name, phone, relation)}``: the primary contact, or failing that the first guardian on file."""
    from families.models import StudentParentRelation

    chosen = {}
    links = (
        StudentParentRelation.objects.filter(student_id__in=student_ids)
        .select_related("parent__profile")
        .order_by("-is_primary_contact", "id")
    )
    for link in links:
        if link.student_id in chosen:
            continue
        profile = link.parent.profile
        chosen[link.student_id] = (
            f"{profile.first_name} {profile.last_name}".strip(),
            profile.phone or profile.alt_phone or "",
            link.relation_type,
        )
    return chosen


def _classes(student_ids):
    """``{student_id: (level, section, level_id, section_id)}`` from each student's current enrolment."""
    from students.models import StudentLevel

    out = {}
    for row in StudentLevel.objects.filter(student_id__in=student_ids, is_current=True).select_related("level", "section"):
        out[row.student_id] = (
            row.level.name if row.level_id else "",
            row.section.name if row.section_id else "",
            row.level_id,
            row.section_id,
        )
    return out


def dues_by_student(*, academic_year=None, level=None, section=None, band=None, search="", sort="amount", today=None,
                    page=1, page_size=25):
    """One row per student with an unpaid fee. Returns ``{"totals", "count", "results"}``.

    A student's *age* is how late their oldest unpaid fee is. Money is aged fee by fee into the band totals, so a
    student with one old fee and one new fee counts each in its own band there."""
    today = today or school_today()
    fees = StudentFee.objects.filter(status="active")
    if academic_year:
        fees = fees.filter(academic_year=academic_year)
    fees = annotate_with_outstanding_balance(fees).filter(_outstanding__gt=0)
    rows = list(fees.values_list("student_id", "_outstanding", "due_date")[:MAX_FEES])

    per_student = {}
    for student_id, amount, due in rows:
        late = (today - due).days if due else 0
        entry = per_student.setdefault(
            student_id,
            {"outstanding": Decimal("0"), "overdue": Decimal("0"), "fees": 0, "oldest": None,
             "bands": {name: Decimal("0") for name in BANDS}},
        )
        entry["outstanding"] += amount
        entry["fees"] += 1
        entry["bands"][band_for(late)] += amount
        if late > 0:
            entry["overdue"] += amount
            if entry["oldest"] is None or due < entry["oldest"]:
                entry["oldest"] = due

    ids = list(per_student)
    classes = _classes(ids)
    if level:
        ids = [i for i in ids if classes.get(i, (None, None, None, None))[2] == level]
    if section:
        ids = [i for i in ids if classes.get(i, (None, None, None, None))[3] == section]

    from students.models import Student

    students = {s.id: s for s in Student.objects.filter(id__in=ids).select_related("profile")}
    guardians = _guardians(ids)
    needle = (search or "").strip().lower()
    out = []
    for student_id in ids:
        student = students.get(student_id)
        if student is None:
            continue
        entry = per_student[student_id]
        days_late = (today - entry["oldest"]).days if entry["oldest"] else 0
        student_band = band_for(days_late)
        name = f"{student.profile.first_name} {student.profile.last_name}".strip()
        if band and student_band != band:
            continue
        if needle and needle not in name.lower() and needle not in (student.enrollment_id or "").lower():
            continue
        guardian = guardians.get(student_id, ("", "", ""))
        klass = classes.get(student_id, ("", "", None, None))
        out.append({
            "student": student_id,
            "name": name,
            "enrollment_id": student.enrollment_id,
            "level": klass[0],
            "section": klass[1],
            "outstanding": entry["outstanding"],
            "overdue": entry["overdue"],
            "fees": entry["fees"],
            "oldest_due": entry["oldest"],
            "days_late": days_late,
            "band": student_band,
            "guardian_name": guardian[0],
            "guardian_phone": guardian[1],
            "guardian_relation": guardian[2],
            "_bands": entry["bands"],
        })

    if sort == "age":
        out.sort(key=lambda r: (-r["days_late"], -r["outstanding"], r["name"]))
    elif sort == "name":
        out.sort(key=lambda r: (r["name"].lower(), r["enrollment_id"]))
    else:
        out.sort(key=lambda r: (-r["outstanding"], r["name"]))

    totals = {
        "students": len(out),
        "outstanding": sum((r["outstanding"] for r in out), Decimal("0")),
        "overdue": sum((r["overdue"] for r in out), Decimal("0")),
        "bands": {name: sum((r["_bands"][name] for r in out), Decimal("0")) for name in BANDS},
        "capped": len(rows) >= MAX_FEES,
    }
    start = (page - 1) * page_size
    shown = out[start:start + page_size]
    for row in out:
        row.pop("_bands")
    return {"totals": totals, "count": len(out), "results": shown}
