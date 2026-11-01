"""Merit lists: students of a class or section ranked by their published result in an examination."""
from .allocation import AllocationError
from .models import ExamResult


def rank_list(examination, *, section=None, level=None, include_failed=False, top=3):
    """Rank the published results of one section, or of a whole class level.

    Ties share a rank and the next rank is skipped (two students on 2nd place are followed by 4th). Students who did
    not pass are listed after the ranked ones without a rank, unless ``include_failed`` ranks them too. Only published
    results are ranked, so a list can never disagree with, or leak ahead of, the published result.
    """
    from students.models import StudentLevel

    if not examination.is_published:
        raise AllocationError("Rank lists are available once the results have been published.")
    if (section is None) == (level is None):
        raise AllocationError("Choose either a section or a class.")

    enrolments = StudentLevel.objects.filter(academic_year=examination.academic_year).select_related("level", "section")
    enrolments = enrolments.filter(section=section) if section is not None else enrolments.filter(level=level)
    # A student can have several rows in the year (for example after a move); the current one wins.
    placed = {}
    for row in enrolments.order_by("is_current"):
        placed[row.student_id] = row

    results = [
        r for r in ExamResult.objects.filter(examination=examination, student_id__in=placed).select_related("student__profile")
    ]
    results.sort(key=lambda r: (-r.percentage, r.student.enrollment_id))

    rows, rank, previous, position = [], None, None, 0
    ranked_pool = [r for r in results if include_failed or r.is_pass]
    unranked = [r for r in results if not (include_failed or r.is_pass)]
    for result in ranked_pool:
        position += 1
        if result.percentage != previous:
            rank, previous = position, result.percentage
        rows.append(_row(result, placed[result.student_id], rank))
    for result in unranked:
        rows.append(_row(result, placed[result.student_id], None))

    return {
        "examination": {"id": examination.id, "name": examination.name, "academic_year": examination.academic_year},
        "scope": "section" if section is not None else "class",
        "title": f"{section.level.name} {section.name}" if section is not None else level.name,
        "include_failed": include_failed,
        "rows": rows,
        "toppers": [r for r in rows if r["rank"] is not None and r["rank"] <= top],
    }


def _row(result, enrolment, rank):
    profile = result.student.profile
    return {
        "rank": rank,
        "student_id": result.student_id,
        "name": f"{profile.first_name} {profile.last_name}".strip(),
        "enrollment_id": result.student.enrollment_id,
        "class": f"{enrolment.level.name} {enrolment.section.name}" if enrolment.section_id else enrolment.level.name,
        "total_marks": result.total_marks_obtained,
        "max_marks": result.total_max_marks,
        "percentage": result.percentage,
        "grade": result.overall_grade,
        "is_pass": result.is_pass,
    }
