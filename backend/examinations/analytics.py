"""Examination analytics from the published results: how a class or section did overall and subject by subject,
how two examinations compare, and which students need help. Only published results are used, so every figure
agrees with the results families see."""
from collections import defaultdict

from .allocation import AllocationError  # noqa: F401  (raised by scoped_results)
from .models import ExamSchedule
from .ranking import scoped_results

# Overall-percentage bands for the mark distribution: (label, from, up to but not including).
BANDS = [
    ("Below 35", 0, 35),
    ("35-49", 35, 50),
    ("50-59", 50, 60),
    ("60-74", 60, 75),
    ("75-89", 75, 90),
    ("90 and above", 90, 1000),
]


def _pct(part, whole):
    return round(part * 100 / whole, 1) if whole else None


def _mean(values):
    return round(sum(values) / len(values), 1) if values else None


def _title(section, level):
    return f"{section.level.name} {section.name}" if section is not None else level.name


def exam_analytics(examination, *, section=None, level=None):
    scoped = scoped_results(examination, section=section, level=level)
    percentages = [float(r.percentage) for r, _ in scoped]
    passed = sum(1 for r, _ in scoped if r.is_pass)

    distribution = [
        {"label": label, "count": sum(1 for p in percentages if low <= p < high)} for label, low, high in BANDS
    ]

    by_section = defaultdict(list)
    for result, enrolment in scoped:
        by_section[enrolment.section_id].append((result, enrolment))
    sections = []
    for rows in by_section.values():
        enrolment = rows[0][1]
        pcts = [float(r.percentage) for r, _ in rows]
        ok = sum(1 for r, _ in rows if r.is_pass)
        sections.append(
            {
                "section": f"{enrolment.level.name} {enrolment.section.name}" if enrolment.section_id else enrolment.level.name,
                "students": len(rows),
                "passed": ok,
                "pass_percentage": _pct(ok, len(rows)),
                "average_percentage": _mean(pcts),
            }
        )
    sections.sort(key=lambda s: s["section"])

    subjects = defaultdict(lambda: {"name": "", "appeared": 0, "absent": 0, "passed": 0, "marks": [], "highest": None, "lowest": None})
    for result, _ in scoped:
        for entry in result.subject_breakdown:
            row = subjects[entry["subject"]]
            row["name"] = entry["subject_name"]
            if entry.get("is_absent"):
                row["absent"] += 1
                continue
            row["appeared"] += 1
            row["passed"] += int(bool(entry.get("is_pass")))
            if entry.get("percentage") is not None:
                value = float(entry["percentage"])
                row["marks"].append(value)
                row["highest"] = value if row["highest"] is None else max(row["highest"], value)
                row["lowest"] = value if row["lowest"] is None else min(row["lowest"], value)
    subject_rows = [
        {
            "subject_id": subject_id,
            "subject": row["name"],
            "appeared": row["appeared"],
            "absent": row["absent"],
            "passed": row["passed"],
            "pass_percentage": _pct(row["passed"], row["appeared"]),
            "average_percentage": _mean(row["marks"]),
            "highest_percentage": row["highest"],
            "lowest_percentage": row["lowest"],
        }
        for subject_id, row in subjects.items()
    ]
    subject_rows.sort(key=lambda r: (r["average_percentage"] is None, r["average_percentage"] or 0, r["subject"]))

    return {
        "examination": {"id": examination.id, "name": examination.name, "academic_year": examination.academic_year},
        "scope": "section" if section is not None else "class",
        "title": _title(section, level),
        "overall": {
            "students": len(scoped),
            "passed": passed,
            "failed": len(scoped) - passed,
            "pass_percentage": _pct(passed, len(scoped)),
            "average_percentage": _mean(percentages),
            "highest_percentage": max(percentages) if percentages else None,
            "lowest_percentage": min(percentages) if percentages else None,
        },
        "distribution": distribution,
        "sections": sections,
        "subjects": subject_rows,  # weakest average first
    }


def compare_examinations(examination, other, *, section=None, level=None):
    """The same class or section in two examinations, subject by subject. ``change`` is other minus examination."""
    first = exam_analytics(examination, section=section, level=level)
    second = exam_analytics(other, section=section, level=level)
    subjects_first = {s["subject_id"]: s for s in first["subjects"]}
    subjects_second = {s["subject_id"]: s for s in second["subjects"]}
    rows = []
    for subject_id in sorted(set(subjects_first) | set(subjects_second), key=lambda i: (subjects_first.get(i) or subjects_second[i])["subject"]):
        a, b = subjects_first.get(subject_id), subjects_second.get(subject_id)
        a_avg = a["average_percentage"] if a else None
        b_avg = b["average_percentage"] if b else None
        rows.append(
            {
                "subject": (a or b)["subject"],
                "first_average": a_avg,
                "second_average": b_avg,
                "change": round(b_avg - a_avg, 1) if a_avg is not None and b_avg is not None else None,
                "first_pass_percentage": a["pass_percentage"] if a else None,
                "second_pass_percentage": b["pass_percentage"] if b else None,
            }
        )
    return {
        "title": first["title"],
        "first": {"name": examination.name, **first["overall"]},
        "second": {"name": other.name, **second["overall"]},
        "subjects": rows,
    }


def weak_students(examination, *, section=None, level=None, margin=5):
    """Students who failed, or passed a subject by less than ``margin`` percentage points, or missed a paper, with
    their attendance beside the marks. Worst first: most failed subjects, then lowest overall result."""
    from .services import get_student_attendance_summary

    scoped = scoped_results(examination, section=section, level=level)
    schedules = ExamSchedule.objects.filter(examination=examination)
    pass_percentage = {
        (s.section_id, str(s.subject_id)): float(s.pass_marks) * 100 / float(s.max_marks) for s in schedules if s.max_marks
    }

    rows = []
    for result, enrolment in scoped:
        weak = []
        for entry in result.subject_breakdown:
            if entry.get("is_absent"):
                weak.append({"subject": entry["subject_name"], "status": "absent", "percentage": None})
            elif not entry.get("is_pass"):
                weak.append({"subject": entry["subject_name"], "status": "failed", "percentage": entry.get("percentage")})
            else:
                bar = pass_percentage.get((enrolment.section_id, entry["subject"]))
                pct = entry.get("percentage")
                if bar is not None and pct is not None and float(pct) < bar + margin:
                    weak.append({"subject": entry["subject_name"], "status": "borderline", "percentage": pct})
        if not weak and result.is_pass:
            continue
        summary = get_student_attendance_summary(result.student_id, examination.academic_year) or {}
        total = summary.get("total_days")
        profile = result.student.profile
        rows.append(
            {
                "student_id": result.student_id,
                "name": f"{profile.first_name} {profile.last_name}".strip(),
                "enrollment_id": result.student.enrollment_id,
                "class": f"{enrolment.level.name} {enrolment.section.name}" if enrolment.section_id else enrolment.level.name,
                "percentage": float(result.percentage),
                "is_pass": result.is_pass,
                "weak_subjects": weak,
                "failed_count": sum(1 for w in weak if w["status"] == "failed"),
                "attendance_percentage": _pct(summary.get("present_days", 0), total) if total else None,
            }
        )
    rows.sort(key=lambda r: (-r["failed_count"], -len(r["weak_subjects"]), r["percentage"], r["name"]))
    return {
        "examination": {"id": examination.id, "name": examination.name},
        "title": _title(section, level),
        "margin": margin,
        "rows": rows,
    }
