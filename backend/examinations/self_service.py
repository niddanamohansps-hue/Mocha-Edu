"""What a student, or a parent of a student, may see about examinations: the date sheet and their own admit card
once the school has announced it, and their section rank when the school chooses to show it."""
from .allocation import build_admit_cards
from .models import ExamSchedule, Examination, ExaminationSettings
from .ranking import rank_list


def _sections_by_year(student):
    from students.models import StudentLevel

    sections = {}
    for row in StudentLevel.objects.filter(student=student).select_related("section__level").order_by("is_current"):
        if row.section_id:
            sections[row.academic_year] = row.section  # a current enrolment overrides an older one of the year
    return sections


def visible_examinations(student):
    """Examinations whose date sheet the school has announced and in which the student's section has papers,
    newest first."""
    sections = _sections_by_year(student)
    visible = []
    for examination in Examination.objects.filter(date_sheet_version__gt=0).order_by("-start_date"):
        section = sections.get(examination.academic_year)
        if section is None or not ExamSchedule.objects.filter(examination=examination, section=section).exists():
            continue
        visible.append(
            {
                "id": examination.id,
                "name": examination.name,
                "academic_year": examination.academic_year,
                "start_date": examination.start_date,
                "end_date": examination.end_date,
                "date_sheet_published_at": examination.date_sheet_published_at,
                "is_published": examination.is_published,
            }
        )
    return visible


def admit_card_for(examination, student):
    """The student's own admit card as ``build_admit_cards`` returns it (one card), or None when the date sheet has
    not been announced, or the student has no papers in this examination."""
    if examination.date_sheet_version < 1:
        return None
    section = _sections_by_year(student).get(examination.academic_year)
    if section is None:
        return None
    data = build_admit_cards(examination, section, only_student=student)
    return data if data["cards"] and data["cards"][0]["papers"] else None


def family_ranks(student, academic_year=None):
    """``{examination_id: {"rank", "of", "section", "examination_name"}}`` for a published result of the student
    that has a rank, or ``{}`` when the school does not show ranks to families."""
    if not ExaminationSettings.load().show_rank_to_families:
        return {}
    from .models import ExamResult

    results = ExamResult.objects.filter(student=student).select_related("examination")
    if academic_year:
        results = results.filter(academic_year=academic_year)
    sections = _sections_by_year(student)
    ranks = {}
    for result in results:
        section = sections.get(result.academic_year)
        if section is None:
            continue
        try:
            listing = rank_list(result.examination, section=section)
        except Exception:
            continue
        mine = next((r for r in listing["rows"] if r["student_id"] == student.id), None)
        if mine is not None and mine["rank"] is not None:
            ranks[str(result.examination_id)] = {
                "rank": mine["rank"],
                "of": len(listing["rows"]),
                "section": listing["title"],
                "examination_name": result.examination.name,
            }
    return ranks
