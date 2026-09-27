"""
Student Promotion & Transfer business logic. Deliberately its own service
layer, never routed through StudentEnrollmentSerializer.update() - that
serializer's "current level" branch edits a StudentLevel row in place and
was never designed to create a second row for a new academic year (see the
approved design report S4). Mirrors the identity-helper-duplication and
select_for_update conventions already established in
attendance/timetable/examinations/fees/services.py.
"""

from decimal import Decimal

from django.db import transaction
from rest_framework import serializers

from academics.models import AcademicLevel, Section
from .models import PromotionRecord, Student, StudentLevel


# --- Identity resolution (duplicated, not imported - students is a peer
# TENANT_APP to attendance/timetable/examinations/fees/parent_portal) ------

def get_profile_for_user(user):
    from profiles.models import Profile

    if not user or not getattr(user, "is_authenticated", False):
        return None
    return Profile.objects.filter(user_id=user.id).first()


def get_staff_member_for_user(user):
    profile = get_profile_for_user(user)
    if not profile:
        return None
    return getattr(profile, "staff_record", None)


# --- Read-only helpers ------------------------------------------------------

def get_promotion_candidates(academic_year, level_id, section_id=None):
    """
    Active students whose CURRENT StudentLevel matches the given
    year/level(/section). Read-only. select_related avoids N+1 on the
    candidates list (student/profile/level/section all needed for display).
    """
    qs = (
        StudentLevel.objects.filter(
            academic_year=academic_year,
            level_id=level_id,
            is_current=True,
            student__status="active",
        )
        .select_related("student__profile", "level", "section")
        .order_by("student__profile__first_name")
    )
    if section_id:
        qs = qs.filter(section_id=section_id)
    return qs


def get_next_level(level):
    """
    AcademicLevel.order + 1 within the same Program, or None if this is
    already the highest-order level (informational only - see design
    report S11: no cross-Program graduation pipeline concept exists, so
    "no next level" is surfaced to the admin as a signal, never enforced).
    """
    if level is None:
        return None
    return (
        AcademicLevel.objects.filter(program_id=level.program_id, order__gt=level.order)
        .order_by("order")
        .first()
    )


def get_fee_warning(student):
    """
    Informational only - total outstanding balance across this student's
    active StudentFee rows, or None if there's nothing owed. Read-only
    dependency on fees (a peer TENANT_APP) - queries its model and reuses
    its pure calculation function directly, exactly mirroring
    parent_portal.views.ChildFeesView's established reuse pattern. Never
    blocks anything - the caller only ever displays this value.
    """
    from fees.models import StudentFee
    from fees.services import get_outstanding_balance

    total = Decimal("0")
    for student_fee in StudentFee.objects.filter(student=student, status="active"):
        total += get_outstanding_balance(student_fee)
    return total if total > 0 else None


def get_exam_warning(student, academic_year):
    """
    Informational only - names of any examinations this student failed in
    the given academic year, derived from the already-published,
    immutable ExamResult snapshot (never recalculated). None if there are
    none. Same reuse pattern as get_fee_warning.
    """
    from examinations.models import ExamResult

    failing = list(
        ExamResult.objects.filter(student=student, academic_year=academic_year, is_pass=False)
        .select_related("examination")
        .values_list("examination__name", flat=True)
    )
    return failing or None


# --- Validation --------------------------------------------------------------

LIFECYCLE_ACTIONS_WITH_NEW_YEAR = ("promoted", "retained")
LIFECYCLE_ACTIONS_TERMINAL = ("transferred", "withdrawn", "graduated")
ALL_LIFECYCLE_ACTIONS = LIFECYCLE_ACTIONS_WITH_NEW_YEAR + LIFECYCLE_ACTIONS_TERMINAL


def validate_academic_year(value):
    """
    Deliberately minimal, matching the project-wide free-text academic_year
    convention (no AcademicYear model exists or is introduced here) - only
    rejects blank/oversized/whitespace-only values, no format policy.
    """
    value = (value or "").strip()
    if not value:
        raise serializers.ValidationError("Academic year is required.")
    if len(value) > 20:
        raise serializers.ValidationError("Academic year must be 20 characters or fewer.")
    return value


def _validate_entry(entry, current, seen_targets):
    """
    Returns an error string, or None if the entry is valid. Never raises -
    callers use this to build a per-student skip/success list rather than
    aborting the whole batch (a hard requirement: one invalid student must
    never abort an otherwise-valid large batch).
    """
    student = entry["student"]
    action = entry["action"]

    if current is None:
        return "This student has no current enrollment to act on."

    if student.status != "active":
        return f"Student status is '{student.status}', not active - cannot process."

    if action in LIFECYCLE_ACTIONS_WITH_NEW_YEAR:
        target_year = entry.get("target_academic_year", "")
        try:
            target_year = validate_academic_year(target_year)
        except serializers.ValidationError as e:
            return str(e.detail[0]) if isinstance(e.detail, list) else str(e.detail)

        if target_year == current.academic_year:
            return "Target academic year must differ from the source academic year."

        if (student.id, target_year) in seen_targets:
            return f"Duplicate entry for this student and target year ({target_year}) in the same batch."

        if StudentLevel.objects.filter(student=student, academic_year=target_year).exists():
            return f"A StudentLevel already exists for this student in {target_year}."

        if action == "retained":
            target_level = current.level
        else:
            target_level = entry.get("target_level_obj") or get_next_level(current.level)

        if target_level is None:
            return "No next level exists for this student's current level, and no explicit target level was provided."

        target_section = entry.get("target_section_obj")
        if target_section is not None and target_section.level_id != target_level.id:
            return "Target section does not belong to the target level."

        entry["_resolved_target_year"] = target_year
        entry["_resolved_target_level"] = target_level
        entry["_resolved_target_section"] = target_section
        return None

    if action in LIFECYCLE_ACTIONS_TERMINAL:
        return None

    return f"Unknown action: {action}"


def _lock_current_rows(entries):
    """
    select_related("level"/"section") cannot be combined with
    select_for_update() here - both are nullable FKs on StudentLevel, and
    PostgreSQL rejects "FOR UPDATE" together with the LEFT OUTER JOIN that
    select_related would generate for them ("FOR UPDATE cannot be applied
    to the nullable side of an outer join" - a real, discovered-via-test
    Postgres restriction, not a hypothetical one). Bulk-fetch the level/
    section objects separately instead and populate Django's FK cache on
    each row manually, avoiding both the SQL error and any N+1 queries.
    """
    student_ids = sorted({str(e["student"].id) for e in entries})
    rows = list(
        StudentLevel.objects.select_for_update()
        .filter(student_id__in=student_ids, is_current=True)
        .select_related("student")
        .order_by("student_id")
    )

    level_ids = {row.level_id for row in rows if row.level_id}
    section_ids = {row.section_id for row in rows if row.section_id}
    levels_by_id = {lvl.id: lvl for lvl in AcademicLevel.objects.filter(id__in=level_ids)}
    sections_by_id = {sec.id: sec for sec in Section.objects.filter(id__in=section_ids)}

    for row in rows:
        if row.level_id:
            row.level = levels_by_id.get(row.level_id)
        if row.section_id:
            row.section = sections_by_id.get(row.section_id)

    return {row.student_id: row for row in rows}


def preview_lifecycle_actions(*, entries):
    """
    Pure computation - performs NO database writes (no select_for_update
    either, since nothing is being written; a plain read is sufficient for
    a preview and avoids holding locks outside a real transaction).
    """
    current_by_student = {
        row.student_id: row
        for row in StudentLevel.objects.filter(
            student_id__in=[e["student"].id for e in entries], is_current=True
        ).select_related("student", "level", "section")
    }

    seen_targets = set()
    results = []
    for entry in entries:
        student = entry["student"]
        current = current_by_student.get(student.id)
        error = _validate_entry(entry, current, seen_targets)

        warnings = []
        if current is not None:
            fee_warning = get_fee_warning(student)
            if fee_warning:
                warnings.append(f"Outstanding fees: {fee_warning}")
            exam_warning = get_exam_warning(student, current.academic_year)
            if exam_warning:
                warnings.append(f"Failed examination(s): {', '.join(exam_warning)}")

        if error is None and entry["action"] in LIFECYCLE_ACTIONS_WITH_NEW_YEAR:
            seen_targets.add((student.id, entry["_resolved_target_year"]))

        results.append(
            {
                "student": str(student.id),
                "action": entry["action"],
                "eligible": error is None,
                "conflicts": [error] if error else [],
                "warnings": warnings,
                "source_academic_year": current.academic_year if current else None,
                "target_academic_year": entry.get("_resolved_target_year"),
                "target_level": str(entry["_resolved_target_level"].id)
                if error is None and entry.get("_resolved_target_level")
                else None,
                "target_section": str(entry["_resolved_target_section"].id)
                if error is None and entry.get("_resolved_target_section")
                else None,
            }
        )
    return results


@transaction.atomic
def execute_lifecycle_actions(*, entries, created_by):
    """
    The atomic bulk operation. All current StudentLevel rows referenced by
    this batch are locked (select_for_update, in stable student-id order -
    matching fees.services.record_payment's exact deadlock-avoidance
    discipline) BEFORE any validation happens, so once validation passes
    for an entry, the state it validated against cannot change out from
    under it before this transaction commits - no per-student savepoints
    are needed for that reason. What CAN still legitimately vary per
    student is validation outcome itself (duplicate target year, wrong
    status, etc.) - those are collected as skips, not exceptions, so one
    bad student never aborts the batch.

    Uses bulk_create/bulk_update for the actual writes once every entry in
    the batch has been validated against the locked state, avoiding one
    round-trip per student at the scale this must support (~10,000
    students) while keeping full correctness - Postgres returns
    auto-generated primary keys from bulk_create, so newly created
    StudentLevel rows can still be referenced by id when building the
    PromotionRecord rows that follow in the same transaction.
    """
    current_by_student = _lock_current_rows(entries)

    seen_targets = set()
    valid = []
    results = []

    for entry in entries:
        student = entry["student"]
        current = current_by_student.get(student.id)
        error = _validate_entry(entry, current, seen_targets)

        if error:
            results.append({"student": str(student.id), "action": entry["action"], "status": "skipped", "error": error})
            continue

        if entry["action"] in LIFECYCLE_ACTIONS_WITH_NEW_YEAR:
            seen_targets.add((student.id, entry["_resolved_target_year"]))

        valid.append((entry, current))

    new_levels = []
    to_deactivate_ids = []
    students_to_update = []
    record_specs = []

    for entry, current in valid:
        action = entry["action"]
        student = entry["student"]
        to_deactivate_ids.append(current.id)

        if action in LIFECYCLE_ACTIONS_WITH_NEW_YEAR:
            new_row = StudentLevel(
                student=student,
                level=entry["_resolved_target_level"],
                section=entry.get("_resolved_target_section"),
                academic_year=entry["_resolved_target_year"],
                is_current=True,
            )
            new_levels.append(new_row)
            record_specs.append((entry, current, new_row))
        else:
            student.status = action
            students_to_update.append(student)
            record_specs.append((entry, current, None))

    if new_levels:
        StudentLevel.objects.bulk_create(new_levels)
    if to_deactivate_ids:
        StudentLevel.objects.filter(id__in=to_deactivate_ids).update(is_current=False)
    if students_to_update:
        Student.objects.bulk_update(students_to_update, ["status"])

    record_objs = [
        PromotionRecord(
            student=entry["student"],
            action=entry["action"],
            source_academic_year=current.academic_year,
            target_academic_year=entry.get("_resolved_target_year", ""),
            source_level=current.level,
            target_level=new_row.level if new_row else None,
            source_section=current.section,
            target_section=new_row.section if new_row else None,
            source_student_level=current,
            target_student_level=new_row,
            reason=entry.get("reason", ""),
            created_by=created_by,
        )
        for entry, current, new_row in record_specs
    ]
    created_records = PromotionRecord.objects.bulk_create(record_objs)

    for i, (entry, current, new_row) in enumerate(record_specs):
        results.append(
            {
                "student": str(entry["student"].id),
                "action": entry["action"],
                "status": "success",
                "record_id": str(created_records[i].id),
            }
        )

    return results


@transaction.atomic
def reverse_promotion(*, record, created_by):
    """
    Reverses a single promoted/retained PromotionRecord (per the approved
    scope - reversal applies to promotion/retention only, not to
    transfer/withdrawal/graduation). Rejects if the state has changed in a
    way that makes a safe reversal impossible. Never deletes the original
    record - creates a new one with action="reversed".
    """
    if record.action not in LIFECYCLE_ACTIONS_WITH_NEW_YEAR:
        raise serializers.ValidationError(
            "Only 'promoted' or 'retained' records can be reversed."
        )
    if hasattr(record, "reversal"):
        raise serializers.ValidationError("This record has already been reversed.")
    if record.target_student_level_id is None:
        raise serializers.ValidationError("This record has no target enrollment to reverse.")

    target_row = StudentLevel.objects.select_for_update().get(id=record.target_student_level_id)
    if not target_row.is_current:
        raise serializers.ValidationError(
            "This student's enrollment has changed since this action - it can no longer be safely reversed."
        )

    source_row = None
    if record.source_student_level_id is not None:
        source_row = StudentLevel.objects.select_for_update().get(id=record.source_student_level_id)

    target_row.is_current = False
    target_row.save(update_fields=["is_current"])
    if source_row is not None:
        source_row.is_current = True
        source_row.save(update_fields=["is_current"])

    reversal = PromotionRecord.objects.create(
        student=record.student,
        action="reversed",
        source_academic_year=record.target_academic_year,
        target_academic_year=record.source_academic_year,
        source_level=record.target_level,
        target_level=record.source_level,
        source_section=record.target_section,
        target_section=record.source_section,
        source_student_level=target_row,
        target_student_level=source_row,
        reason=f"Reversal of promotion record {record.id}",
        created_by=created_by,
        reverses=record,
    )
    return reversal
