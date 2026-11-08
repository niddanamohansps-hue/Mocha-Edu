"""Supplementary (re-sit) examinations.

A supplementary examination is an ordinary examination linked to a published original. Starting one lists, from the
original's published results, every student who failed or missed a subject, and what they may re-sit. The school
schedules the papers with the normal schedule screen and enters marks as usual, but a re-sit paper accepts marks only
for the students entitled to it. Results of the re-sit are published like any other, and sit beside the original on
the report card: the original result is never changed.
"""
from django.db import transaction

from core.audit import log_action

from .models import Examination, ExamResult, SupplementaryCandidate


class SupplementaryError(Exception):
    """The request cannot be done. Nothing was changed."""


@transaction.atomic
def start_supplementary(original, *, name, exam_type, start_date, end_date, user, request=None):
    original = Examination.objects.select_for_update().get(pk=original.pk)
    if not original.is_published:
        raise SupplementaryError("Results must be published before a supplementary examination can be started.")
    if original.supplementary_of_id:
        raise SupplementaryError("A supplementary examination cannot have its own supplementary examination.")
    if Examination.objects.filter(supplementary_of=original).exists():
        raise SupplementaryError("A supplementary examination has already been started for this examination.")
    name = (name or "").strip()
    if not name:
        raise SupplementaryError("Give the supplementary examination a name.")
    if not start_date or not end_date or start_date > end_date:
        raise SupplementaryError("Choose a start date that is not after the end date.")

    candidates = []
    for result in ExamResult.objects.filter(examination=original).select_related("student"):
        for entry in result.subject_breakdown:
            if entry.get("is_pass"):
                continue
            candidates.append(
                {
                    "student_id": result.student_id,
                    "subject_id": entry["subject"],
                    "reason": SupplementaryCandidate.Reason.ABSENT if entry.get("is_absent") else SupplementaryCandidate.Reason.FAILED,
                    "original_percentage": entry.get("percentage"),
                }
            )
    if not candidates:
        raise SupplementaryError("Nobody failed or missed a subject, so there is nothing to re-sit.")

    supplementary = Examination.objects.create(
        academic_year=original.academic_year, academic_year_ref=original.academic_year_ref, name=name, exam_type=exam_type,
        start_date=start_date, end_date=end_date, supplementary_of=original,
    )
    SupplementaryCandidate.objects.bulk_create(
        [
            SupplementaryCandidate(
                examination=supplementary, student_id=c["student_id"], subject_id=c["subject_id"], reason=c["reason"],
                original_percentage=c["original_percentage"],
            )
            for c in candidates
        ]
    )
    log_action(
        request, "supplementary_started", "Examination", str(supplementary.id),
        {"original": str(original.id), "candidates": len(candidates)},
    )
    return supplementary


def candidate_student_ids(examination_id, subject_id):
    """The students (as strings, like the roster helper) entitled to re-sit one subject in this examination."""
    return {
        str(s) for s in SupplementaryCandidate.objects.filter(examination_id=examination_id, subject_id=subject_id)
        .values_list("student_id", flat=True)
    }


def candidates_data(examination):
    """Who may re-sit what, and, once the re-sit is published, whether each cleared the subject."""
    from students.models import StudentLevel

    results = {}
    if examination.is_published:
        for result in ExamResult.objects.filter(examination=examination):
            results[result.student_id] = {e["subject"]: e for e in result.subject_breakdown}

    placement = {}
    original = examination.supplementary_of
    year = original.academic_year if original else examination.academic_year
    for row in StudentLevel.objects.filter(academic_year=year).select_related("level", "section").order_by("is_current"):
        placement[row.student_id] = row

    rows = []
    for candidate in examination.supplementary_candidates.select_related("student__profile", "subject"):
        entry = results.get(candidate.student_id, {}).get(str(candidate.subject_id))
        place = placement.get(candidate.student_id)
        profile = candidate.student.profile
        rows.append(
            {
                "student_id": candidate.student_id,
                "name": f"{profile.first_name} {profile.last_name}".strip(),
                "enrollment_id": candidate.student.enrollment_id,
                "class": (f"{place.level.name} {place.section.name}" if place and place.section_id else (place.level.name if place else "")),
                "subject_id": candidate.subject_id,
                "subject": candidate.subject.name,
                "reason": candidate.reason,
                "original_percentage": candidate.original_percentage,
                "resit_percentage": entry.get("percentage") if entry else None,
                "cleared": (bool(entry.get("is_pass")) if entry else None),
            }
        )
    rows.sort(key=lambda r: (r["class"], r["subject"], r["enrollment_id"]))
    summary = {
        "candidates": len(rows),
        "students": len({r["student_id"] for r in rows}),
        "cleared": sum(1 for r in rows if r["cleared"] is True),
        "not_cleared": sum(1 for r in rows if r["cleared"] is False),
        "waiting": sum(1 for r in rows if r["cleared"] is None),
    }
    return {
        "examination": {
            "id": examination.id, "name": examination.name, "is_published": examination.is_published,
            "start_date": examination.start_date, "end_date": examination.end_date,
        },
        "original": ({"id": original.id, "name": original.name} if original else None),
        "summary": summary,
        "rows": rows,
    }
