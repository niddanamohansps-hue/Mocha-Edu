"""
Examination business logic and object-level authorization. All domain rules
live here (never scattered across serializers/views), mirroring the exact
pattern established in attendance/services.py and timetable/services.py.
"""

from decimal import Decimal

from django.db import transaction
from rest_framework import serializers


# --- Identity resolution -----------------------------------------------
# Duplicated from attendance/services.py and timetable/services.py rather
# than imported cross-app - all three are peer TENANT_APPS and none should
# depend on another. Consolidate into core only once a 4th module needs the
# same helpers (not before - three independent copies is still cheaper than
# a premature shared abstraction).

def get_profile_for_user(user):
    from profiles.models import Profile

    if not user or not getattr(user, "is_authenticated", False):
        return None
    return Profile.objects.filter(user_id=user.id).first()


def get_student_for_user(user):
    profile = get_profile_for_user(user)
    if not profile:
        return None
    return getattr(profile, "student_record", None)


def get_staff_member_for_user(user):
    profile = get_profile_for_user(user)
    if not profile:
        return None
    return getattr(profile, "staff_record", None)


def get_instructor_for_user(user):
    staff_member = get_staff_member_for_user(user)
    if not staff_member:
        return None
    return getattr(staff_member, "instructor_record", None)


def is_owner(request):
    from roles.models import UserRole

    if getattr(request.user, "is_superuser", False):
        return True
    tenant = getattr(request, "tenant", None)
    if not tenant or tenant.schema_name == "public":
        return False
    return UserRole.objects.filter(user=request.user, role__slug="owner").exists()


# --- Object-level authorization -----------------------------------------

def user_can_access_schedule(request, schedule):
    """
    - Owner bypasses.
    - An Instructor-record holder may only access a schedule where
      SubjectAssignment(section=schedule.section, subject=schedule.subject,
      instructor=self) exists - an instructor can never touch another
      instructor's schedule, even for the same section (if they don't
      teach that subject there).
    - Everyone else with the relevant permission gets tenant-wide access,
      consistent with the "staff" role treatment in Attendance/Timetable.
    """
    if is_owner(request):
        return True

    instructor = get_instructor_for_user(request.user)
    if instructor is not None:
        from academics.models import SubjectAssignment

        return SubjectAssignment.objects.filter(
            section_id=schedule.section_id, subject_id=schedule.subject_id, instructor=instructor
        ).exists()

    return True


def user_can_access_student_result(request, student):
    """
    A student may only ever read their own result. Anyone else needs the
    relevant permission (checked separately by the view) plus, if an
    instructor, a SubjectAssignment tying them to at least one of that
    student's current sections - mirroring attendance's exact rule for
    student-record access.
    """
    own_student = get_student_for_user(request.user)
    if own_student is not None:
        return own_student.id == student.id

    if is_owner(request):
        return True

    instructor = get_instructor_for_user(request.user)
    if instructor is not None:
        from academics.models import SubjectAssignment

        current_section_ids = student.enrollments.filter(is_current=True).values_list(
            "section_id", flat=True
        )
        return SubjectAssignment.objects.filter(
            section_id__in=current_section_ids, instructor=instructor
        ).exists()

    return True


def get_section_roster_student_ids(section_id):
    """
    Currently-enrolled, active students for a section - same pattern as
    attendance.services.get_section_roster / timetable's roster resolution.
    Never Student.objects.all().
    """
    from students.models import Student

    return set(
        str(s)
        for s in Student.objects.filter(
            enrollments__section_id=section_id, enrollments__is_current=True, status="active"
        ).values_list("id", flat=True)
    )


# --- ExamSchedule validation ---------------------------------------------

def validate_exam_schedule(*, examination, subject, section, academic_year, date, start_time, end_time, period, room, exclude_id=None):
    """
    Runs every "before create/update" rule for an ExamSchedule. Raises
    serializers.ValidationError with a clear, field-scoped message.

    Deliberately does NOT check conflicts against timetable.TimetableEntry -
    regular timetable is not authoritative on examination days (classes are
    commonly suspended), so cross-referencing it would produce false-positive
    conflicts with no calendar context to resolve them.
    """
    if examination.academic_year != academic_year:
        raise serializers.ValidationError(
            {"academic_year": "Schedule academic year must match the examination's academic year."}
        )

    if subject.level_id != section.level_id:
        raise serializers.ValidationError(
            {"subject": "Selected subject does not belong to this section's academic level."}
        )

    if period is not None and period.academic_year != academic_year:
        raise serializers.ValidationError(
            {"period": "Selected period does not belong to this schedule's academic year."}
        )

    if start_time >= end_time:
        raise serializers.ValidationError({"start_time": "Start time must be before end time."})

    if date < examination.start_date or date > examination.end_date:
        raise serializers.ValidationError(
            {"date": "Exam date must fall within the examination's date range."}
        )

    from .models import ExamSchedule

    overlap_qs = ExamSchedule.objects.filter(date=date).filter(
        start_time__lt=end_time, end_time__gt=start_time
    )
    if exclude_id:
        overlap_qs = overlap_qs.exclude(id=exclude_id)

    if overlap_qs.filter(section=section).exists():
        raise serializers.ValidationError(
            {"section": "This section already has an overlapping exam scheduled at this time."}
        )

    if room is not None and overlap_qs.filter(room=room).exists():
        raise serializers.ValidationError(
            {"room": "This room is already booked for another exam at this time."}
        )


# --- Grading & result calculation -----------------------------------------

def calculate_grade(percentage, academic_year):
    """Returns (grade_label, grade_point) or (None, None) if no boundary matches."""
    from .models import GradeBoundary

    boundary = GradeBoundary.objects.filter(
        academic_year=academic_year, min_percentage__lte=percentage, max_percentage__gte=percentage
    ).first()
    if boundary:
        return boundary.grade_label, boundary.grade_point
    return None, None


def effective_marks(mark, schedule):
    """Marks that count for a result: obtained plus grace, capped at the maximum; None when not marked or not sat."""
    if mark.marks_obtained is None or mark.is_absent or mark.attendance != "present":
        return None
    return min(mark.marks_obtained + (mark.grace_marks or 0), schedule.max_marks)


def is_exempt(mark):
    """An exempt student's subject counts for nothing: no marks, no maximum, no pass or fail."""
    return mark is not None and mark.attendance == "exempt"


def calculate_subject_result(exam_mark, exam_schedule):
    """
    Dynamic (pre-publication) per-subject result for one student, and also
    the shape snapshotted into ExamResult.subject_breakdown at publish time.
    Supports both flat single-score papers and multi-component assessments
    (Theory, Practical, Internal Assessment) with separate pass requirements.
    """
    components = list(exam_schedule.components.all())
    has_components = bool(components)
    max_marks = (
        sum((c.max_marks for c in components), Decimal("0"))
        if has_components
        else exam_schedule.max_marks
    )
    pass_marks = exam_schedule.pass_marks

    extra = {
        "attendance": exam_mark.attendance if exam_mark is not None else "absent",
        "grace_marks": float(exam_mark.grace_marks or 0) if exam_mark is not None else 0.0,
    }

    components_breakdown = []
    failed_separate_pass = False

    if has_components:
        comp_marks_map = (
            {cm.component_id: cm for cm in exam_mark.component_marks.all()}
            if exam_mark is not None
            else {}
        )
        for comp in components:
            cm = comp_marks_map.get(comp.id)
            c_absent = cm.is_absent if cm is not None else (exam_mark.is_absent if exam_mark else True)
            c_obtained = cm.marks_obtained if (cm is not None and not c_absent) else None
            c_pass = False
            if c_obtained is not None and not c_absent:
                c_pass = c_obtained >= comp.pass_marks
            if comp.requires_separate_pass and not c_pass:
                failed_separate_pass = True

            components_breakdown.append(
                {
                    "component_id": str(comp.id),
                    "name": comp.name,
                    "code": comp.code,
                    "is_theory": comp.is_theory,
                    "requires_separate_pass": comp.requires_separate_pass,
                    "max_marks": float(comp.max_marks),
                    "pass_marks": float(comp.pass_marks),
                    "marks_obtained": float(c_obtained) if c_obtained is not None else None,
                    "is_absent": c_absent,
                    "is_pass": c_pass,
                }
            )

    if exam_mark is None or exam_mark.is_absent:
        res = {
            "subject": str(exam_schedule.subject_id),
            "subject_name": exam_schedule.subject.name,
            "marks_obtained": None,
            "max_marks": float(max_marks),
            "percentage": None,
            "grade": None,
            "is_absent": True,
            "is_pass": False,
            **extra,
        }
        if has_components:
            res["components"] = components_breakdown
        return res

    obtained = effective_marks(exam_mark, exam_schedule)
    if has_components and components_breakdown:
        all_comp_obtained = [
            c["marks_obtained"]
            for c in components_breakdown
            if c["marks_obtained"] is not None
        ]
        if all_comp_obtained:
            comp_sum = sum(Decimal(str(m)) for m in all_comp_obtained)
            obtained = min(comp_sum + (exam_mark.grace_marks or 0), max_marks)
        elif exam_mark.attendance != "present":
            obtained = None

    if obtained is None:
        res = {
            "subject": str(exam_schedule.subject_id),
            "subject_name": exam_schedule.subject.name,
            "marks_obtained": None,
            "max_marks": float(max_marks),
            "percentage": None,
            "grade": None,
            "is_absent": False,
            "is_pass": False,
            **extra,
        }
        if has_components:
            res["components"] = components_breakdown
        return res

    percentage = round(float(obtained / max_marks) * 100, 2)
    grade_label, _ = calculate_grade(percentage, exam_schedule.academic_year)
    is_pass = (obtained >= pass_marks) and not failed_separate_pass

    res = {
        "subject": str(exam_schedule.subject_id),
        "subject_name": exam_schedule.subject.name,
        "marks_obtained": float(obtained),
        "max_marks": float(max_marks),
        "percentage": percentage,
        "grade": grade_label,
        "is_absent": False,
        "is_pass": is_pass,
        **extra,
    }
    if has_components:
        res["components"] = components_breakdown
    return res


def calculate_student_examination_result(examination, student):
    """
    Equal-weighted aggregate across every ExamSchedule of this examination
    that the student has a mark row for (schedules with no mark at all for
    this student are treated as not-applicable, not as a zero - e.g. the
    student wasn't enrolled in that subject).
    """
    from .models import ExamMark, ExamSchedule

    schedules = (
        ExamSchedule.objects.filter(examination=examination)
        .select_related("subject")
        .prefetch_related("components")
    )
    marks_by_schedule = {
        m.exam_schedule_id: m
        for m in ExamMark.objects.filter(
            exam_schedule__examination=examination, student=student
        ).prefetch_related("component_marks__component")
    }

    breakdown = []
    total_obtained = Decimal("0")
    total_max = Decimal("0")
    any_fail = False
    participated = False

    for schedule in schedules:
        mark = marks_by_schedule.get(schedule.id)
        if mark is None or is_exempt(mark):
            continue
        participated = True
        subject_result = calculate_subject_result(mark, schedule)
        breakdown.append(subject_result)

        sched_max = Decimal(str(subject_result["max_marks"]))
        if subject_result["is_absent"] or subject_result["marks_obtained"] is None:
            any_fail = True
            total_max += sched_max
            continue

        total_obtained += Decimal(str(subject_result["marks_obtained"]))
        total_max += sched_max
        if not subject_result["is_pass"]:
            any_fail = True

    if not participated or total_max == 0:
        return None

    percentage = round(float(total_obtained / total_max) * 100, 2)
    overall_grade, _ = calculate_grade(percentage, examination.academic_year)

    return {
        "total_marks_obtained": total_obtained,
        "total_max_marks": total_max,
        "percentage": Decimal(str(percentage)),
        "overall_grade": overall_grade or "",
        "is_pass": not any_fail,
        "subject_breakdown": breakdown,
    }


def calculate_examination_results_bulk(examination, students):
    """
    Bulk sibling of calculate_student_examination_result(), used ONLY by
    publish_examination() to eliminate its per-student N+1.
    """
    from .models import ExamMark, ExamSchedule, GradeBoundary

    schedules = list(
        ExamSchedule.objects.filter(examination=examination)
        .select_related("subject")
        .prefetch_related("components")
    )

    student_ids = [student.id for student in students]
    marks_by_student = {}
    for mark in ExamMark.objects.filter(
        exam_schedule__examination=examination, student_id__in=student_ids
    ).prefetch_related("component_marks__component"):
        marks_by_student.setdefault(mark.student_id, {})[mark.exam_schedule_id] = mark

    boundaries = list(
        GradeBoundary.objects.filter(academic_year=examination.academic_year).order_by("-min_percentage")
    )

    def grade_for(percentage):
        exact = Decimal(str(percentage))
        for boundary in boundaries:
            if boundary.min_percentage <= exact <= boundary.max_percentage:
                return boundary.grade_label
        return None

    results = {}
    for student in students:
        marks_by_schedule = marks_by_student.get(student.id, {})

        breakdown = []
        total_obtained = Decimal("0")
        total_max = Decimal("0")
        any_fail = False
        participated = False

        for schedule in schedules:
            mark = marks_by_schedule.get(schedule.id)
            if mark is None or is_exempt(mark):
                continue
            participated = True

            components = list(schedule.components.all())
            has_components = bool(components)
            max_marks = (
                sum((c.max_marks for c in components), Decimal("0"))
                if has_components
                else schedule.max_marks
            )
            pass_marks = schedule.pass_marks

            components_breakdown = []
            failed_separate_pass = False

            if has_components:
                comp_marks_map = (
                    {cm.component_id: cm for cm in mark.component_marks.all()}
                    if mark is not None
                    else {}
                )
                for comp in components:
                    cm = comp_marks_map.get(comp.id)
                    c_absent = cm.is_absent if cm is not None else (mark.is_absent if mark else True)
                    c_obtained = cm.marks_obtained if (cm is not None and not c_absent) else None
                    c_pass = False
                    if c_obtained is not None and not c_absent:
                        c_pass = c_obtained >= comp.pass_marks
                    if comp.requires_separate_pass and not c_pass:
                        failed_separate_pass = True

                    components_breakdown.append(
                        {
                            "component_id": str(comp.id),
                            "name": comp.name,
                            "code": comp.code,
                            "is_theory": comp.is_theory,
                            "requires_separate_pass": comp.requires_separate_pass,
                            "max_marks": float(comp.max_marks),
                            "pass_marks": float(comp.pass_marks),
                            "marks_obtained": float(c_obtained) if c_obtained is not None else None,
                            "is_absent": c_absent,
                            "is_pass": c_pass,
                        }
                    )

            obtained = effective_marks(mark, schedule)
            if has_components and components_breakdown:
                all_comp_obtained = [
                    c["marks_obtained"]
                    for c in components_breakdown
                    if c["marks_obtained"] is not None
                ]
                if all_comp_obtained:
                    comp_sum = sum(Decimal(str(m)) for m in all_comp_obtained)
                    obtained = min(comp_sum + (mark.grace_marks or 0), max_marks)
                elif mark.attendance != "present":
                    obtained = None

            extra = {"attendance": mark.attendance, "grace_marks": float(mark.grace_marks or 0)}

            if obtained is None:
                item = {
                    "subject": str(schedule.subject_id),
                    "subject_name": schedule.subject.name,
                    "marks_obtained": None,
                    "max_marks": float(max_marks),
                    "percentage": None,
                    "grade": None,
                    "is_absent": mark.is_absent,
                    "is_pass": False,
                    **extra,
                }
                if has_components:
                    item["components"] = components_breakdown
                breakdown.append(item)
                any_fail = True
                total_max += max_marks
                continue

            subject_percentage = round(float(obtained / max_marks) * 100, 2)
            grade_label = grade_for(subject_percentage)
            is_pass = (obtained >= pass_marks) and not failed_separate_pass
            item = {
                "subject": str(schedule.subject_id),
                "subject_name": schedule.subject.name,
                "marks_obtained": float(obtained),
                "max_marks": float(max_marks),
                "percentage": subject_percentage,
                "grade": grade_label,
                "is_absent": False,
                "is_pass": is_pass,
                **extra,
            }
            if has_components:
                item["components"] = components_breakdown
            breakdown.append(item)
            total_obtained += obtained
            total_max += max_marks
            if not is_pass:
                any_fail = True

        if not participated or total_max == 0:
            results[student.id] = None
            continue

        overall_percentage = round(float(total_obtained / total_max) * 100, 2)
        overall_grade = grade_for(overall_percentage)

        results[student.id] = {
            "total_marks_obtained": total_obtained,
            "total_max_marks": total_max,
            "percentage": Decimal(str(overall_percentage)),
            "overall_grade": overall_grade or "",
            "is_pass": not any_fail,
            "subject_breakdown": breakdown,
        }

    return results


def _build_portal_link(path):
    """
    Builds an absolute link to the tenant's own frontend, for use in a
    notification email body. Reuses PASSWORD_RESET_FRONTEND_PROTOCOL/PORT
    (accounts/views.py's ForgotPasswordView) rather than introducing a
    second frontend-URL setting - both features point at the same
    tenant_frontend app on the same port, just different paths.

    Unlike the password-reset flow, there is no inbound HTTP request here
    to read the tenant's host from (this runs from publish_examination(),
    a plain service function) - the tenant's own primary Domain row
    (already the source of truth for tenant routing) is the equivalent
    source of the hostname. Falls back to a bare relative path if, for
    whatever reason, the current connection has no tenant/domain - still a
    usable (if non-clickable-without-context) instruction in the email.
    """
    from django.conf import settings
    from django.db import connection

    tenant = connection.tenant
    domain = tenant.domains.filter(is_primary=True).first() if tenant else None
    if domain is None and tenant is not None:
        domain = tenant.domains.first()
    if domain is None:
        return path

    port_suffix = (
        f":{settings.PASSWORD_RESET_FRONTEND_PORT}" if settings.PASSWORD_RESET_FRONTEND_PORT else ""
    )
    return f"{settings.PASSWORD_RESET_FRONTEND_PROTOCOL}://{domain.domain}{port_suffix}{path}"


def _resolve_result_notification_recipients(student):
    """
    Returns a list of {"email", "is_parent"} dicts eligible for a
    result-published notification for this one student: their own portal
    account (profiles.Profile.user, the existing soft-link to
    accounts.User) if linked and has an email, plus every parent/guardian
    linked via families.StudentParentRelation whose own portal account
    likewise has an email.

    Deliberately skips anyone with no linked portal account/email rather
    than inventing a new contact concept - "only send to recipients for
    whom the application already has a valid email relationship" is
    exactly what Profile.user_id being unset (common for a Student created
    without ever activating a portal login) already represents.
    """
    recipients = []

    student_user = student.profile.user
    if student_user and student_user.email:
        recipients.append({"email": student_user.email, "is_parent": False})

    from families.models import StudentParentRelation

    parent_links = StudentParentRelation.objects.filter(student=student).select_related("parent__profile")
    for link in parent_links:
        parent_user = link.parent.profile.user
        if parent_user and parent_user.email:
            recipients.append({"email": parent_user.email, "is_parent": True})

    return recipients


def _queue_result_published_notifications(examination, student_ids):
    """
    Queues one result-published email per eligible recipient (see
    _resolve_result_notification_recipients) for every student in
    student_ids, via the existing async outbox (notifications.services.
    queue_email) - the exact same call accounts.views.ForgotPasswordView
    already uses, so no second notification mechanism is introduced.

    Content is deliberately minimal - exam name only, never marks/grades/
    percentage - the recipient must log in to the existing authenticated
    portal (StudentReportCardView / parent_portal's child-results views)
    to see the actual result.

    Idempotency: this is only ever called from inside publish_examination()'s
    own atomic block, which itself can only run once per Examination (see
    the is_published guard below) - so this function can never run twice
    for the same examination, and no separate dedupe key is needed.

    Must NOT be wrapped in a broad except/pass: queue_email() only writes
    an EmailOutboxEvent row and defers a Celery dispatch via
    transaction.on_commit() - it never sends an email synchronously, so
    anything it raises here is a genuine programming/data error (e.g. a
    database problem), not an "email failed to send" case. Letting it
    propagate (and roll back this function's caller's transaction, same as
    any other failure inside that transaction) is correct; actual delivery
    failures happen later, asynchronously, in tasks.send_outbox_email, and
    are handled entirely by its own retry/failure state machine.
    """
    from notifications.services import queue_email
    from students.models import Student

    students_by_id = {s.id: s for s in Student.objects.filter(id__in=student_ids).select_related("profile")}

    for student_id in student_ids:
        student = students_by_id.get(student_id)
        if student is None:
            continue
        full_name = f"{student.profile.first_name} {student.profile.last_name}"

        for recipient in _resolve_result_notification_recipients(student):
            if recipient["is_parent"]:
                subject = f"Examination results available for {full_name}"
                body = (
                    f"The examination results for {full_name} ({examination.name}) are now available.\n\n"
                    f"Please log in to the parent portal to view the results:\n"
                    f"{_build_portal_link('/dashboard/parent-portal/results')}"
                )
            else:
                subject = "Your examination results are available"
                body = (
                    f"Your examination results for {examination.name} are now available.\n\n"
                    f"Please log in to view your results:\n"
                    f"{_build_portal_link('/dashboard/examinations/results')}"
                )

            queue_email(to_email=recipient["email"], subject=subject, body=body)


def publish_examination(examination):
    """
    Atomically snapshots every participating student's result into
    ExamResult, marks the examination published, and queues a
    result-published notification (see _queue_result_published_notifications)
    for each newly-published student's eligible recipients - all in the
    same transaction. "Participating" means having at least one ExamMark
    row across this examination's schedules - students never marked for
    any of its subjects are not included, and never notified.

    If ANYTHING fails - including a genuine error while queuing
    notifications - nothing is partially published (single transaction):
    no ExamResult rows, no is_published flag, and no EmailOutboxEvent rows
    survive. Actual email DELIVERY, by contrast, can never roll this back -
    queue_email() only writes a row and defers dispatch via
    transaction.on_commit(), so the Celery task that really sends the
    email only ever runs after this transaction has already committed.

    Raises serializers.ValidationError if the examination is already
    published or has no schedules/marks at all.
    """
    from django.utils import timezone

    from .models import ExamMark, ExamResult

    if examination.is_published:
        raise serializers.ValidationError({"non_field_errors": ["This examination is already published."]})

    student_ids = (
        ExamMark.objects.filter(exam_schedule__examination=examination)
        .values_list("student_id", flat=True)
        .distinct()
    )
    if not student_ids:
        raise serializers.ValidationError(
            {"non_field_errors": ["No marks have been entered for this examination yet."]}
        )

    from students.models import Student

    with transaction.atomic():
        students = list(Student.objects.filter(id__in=student_ids))
        # calculate_examination_results_bulk() (not
        # calculate_student_examination_result() in a loop) - see its
        # docstring: same calculation semantics, but schedules/marks/grade
        # boundaries are each loaded ONCE for the whole examination instead
        # of once per student.
        results_by_student = calculate_examination_results_bulk(examination, students)

        published_student_ids = []
        results_to_create = []
        for student in students:
            result = results_by_student.get(student.id)
            if result is None:
                continue
            results_to_create.append(
                ExamResult(
                    examination=examination,
                    student=student,
                    academic_year=examination.academic_year,
                    total_marks_obtained=result["total_marks_obtained"],
                    total_max_marks=result["total_max_marks"],
                    percentage=result["percentage"],
                    overall_grade=result["overall_grade"],
                    is_pass=result["is_pass"],
                    subject_breakdown=result["subject_breakdown"],
                )
            )
            published_student_ids.append(student.id)

        # bulk_create() is safe here: ExamResult has no custom save(), no
        # clean()/full_clean() call, and no connected signals (verified by
        # inspection - unlike GradeBoundary, which does call full_clean()
        # in its own save()). The unique_together=("examination","student")
        # constraint is still enforced by Postgres at INSERT time either
        # way, and each row here is for a distinct student, so no
        # intra-batch collision is possible.
        ExamResult.objects.bulk_create(results_to_create)

        examination.is_published = True
        examination.published_at = timezone.now()
        examination.save(update_fields=["is_published", "published_at", "updated_at"])

        # queue_email() (see notifications.services) now handles a
        # post-commit Celery dispatch failure centrally - it logs and
        # swallows it there, so no CeleryError handling is needed here
        # anymore. A genuine error raised directly by this call (a real
        # DB/programming error, not a dispatch failure) still propagates
        # and rolls back this entire block, exactly as before.
        _queue_result_published_notifications(examination, published_student_ids)

    return examination


# --- Report Cards, Transcripts & Academic Record Helpers -------------------

def get_institution_summary():
    """
    Returns institutional branding and contact information for the current tenant.
    Combines Organization (public tenant row) and InstitutionProfile (tenant schema).
    """
    from django.db import connection
    from profiles.models import InstitutionProfile

    tenant = getattr(connection, "tenant", None)
    if not tenant or getattr(tenant, "schema_name", None) == "public":
        return {
            "name": "Institution",
            "address": "",
            "phone": "",
            "email": "",
            "website": "",
            "tagline": "",
            "logo_url": None,
        }

    profile = InstitutionProfile.objects.filter(organization_id=tenant.id).first()
    logo_url = None
    if profile and profile.logo:
        try:
            logo_url = profile.logo.url
        except Exception:
            logo_url = None

    return {
        "name": tenant.name,
        "address": getattr(tenant, "address", "") or "",
        "phone": getattr(tenant, "phone", "") or "",
        "email": getattr(tenant, "email", "") or "",
        "website": getattr(profile, "website", "") or "",
        "tagline": getattr(profile, "tagline", "") or "",
        "logo_url": logo_url,
    }


def calculate_gpa(subject_breakdown, academic_year):
    """
    Weighted GPA calculation according to school grading configuration:
    GPA = round(sum(grade_point * credits) / sum(credits), 2)

    Rules:
    - GradeBoundary.grade_point is nullable Decimal.
    - Subject.credits is Decimal (defaults to 1.0).
    - If GradeBoundaries do not exist for the academic year, or ANY boundary in that
      academic year has grade_point is None: return None (GPA is unconfigured).
    - If any graded subject in subject_breakdown has no matching boundary, or its
      matching boundary has grade_point is None: return None.
    - If a subject is marked absent or percentage/marks are None: result is incomplete,
      return None.
    - Never silently treat missing grade points as zero.
    - Returns float rounded to 2 decimal places, or None.
    """
    if not subject_breakdown:
        return None

    from academics.models import Subject
    from .models import GradeBoundary

    boundaries = list(GradeBoundary.objects.filter(academic_year=academic_year).order_by("-min_percentage"))
    if not boundaries:
        return None

    # If school hasn't configured grade_point on all boundaries for this year, GPA is unavailable
    if any(b.grade_point is None for b in boundaries):
        return None

    subject_ids = [s.get("subject") for s in subject_breakdown if s.get("subject")]
    subjects_by_id = {
        str(sub.id): sub for sub in Subject.objects.filter(id__in=subject_ids)
    }

    weighted_points = 0.0
    total_credits = 0.0

    for item in subject_breakdown:
        if item.get("is_absent") or item.get("percentage") is None or item.get("grade") is None:
            return None

        # Find matching boundary by grade label, or by percentage
        matching_boundary = None
        for b in boundaries:
            if b.grade_label == item.get("grade"):
                matching_boundary = b
                break
        if not matching_boundary:
            exact_pct = Decimal(str(item.get("percentage")))
            for b in boundaries:
                if b.min_percentage <= exact_pct <= b.max_percentage:
                    matching_boundary = b
                    break

        if not matching_boundary or matching_boundary.grade_point is None:
            return None

        sub_obj = subjects_by_id.get(str(item.get("subject")))
        credits = float(sub_obj.credits) if sub_obj and sub_obj.credits is not None else 1.0
        if credits <= 0:
            continue

        weighted_points += float(matching_boundary.grade_point) * credits
        total_credits += credits

    if total_credits == 0:
        return None

    return round(weighted_points / total_credits, 2)


def get_student_attendance_summary(student_id, academic_year=None):
    """
    Retrieves student attendance summary and percentage via attendance.services.
    """
    from attendance.models import AttendanceSettings, StudentAttendance
    from attendance.services import calculate_attendance_percentage

    qs = StudentAttendance.objects.filter(student_id=student_id).select_related("session")
    if academic_year:
        qs = qs.filter(session__academic_year=academic_year)

    counts = {}
    total_days = 0
    for row in qs:
        counts[row.status] = counts.get(row.status, 0) + 1
        total_days += 1

    try:
        settings = AttendanceSettings.get_solo()
        percentage = calculate_attendance_percentage(counts, settings)
    except Exception:
        percentage = None

    return {
        "percentage": percentage,
        "total_days": total_days,
        "present_days": counts.get("present", 0),
        "absent_days": counts.get("absent", 0),
        "late_days": counts.get("late", 0),
        "half_days": counts.get("half_day", 0),
        "leave_days": counts.get("leave", 0),
        "status_counts": counts,
    }


def get_student_promotion_summary(student_id, academic_year):
    """
    Returns the latest non-reversed promotion transition record where
    source_academic_year matches the given academic year.
    """
    from students.models import PromotionRecord

    records = (
        PromotionRecord.objects.filter(
            student_id=student_id,
            source_academic_year=academic_year,
        )
        .exclude(action="reversed")
        .select_related("source_level", "target_level", "target_section")
        .order_by("-created_at")
    )
    for rec in records:
        if not hasattr(rec, "reversal"):
            return {
                "action": rec.action,
                "action_display": rec.get_action_display(),
                "source_level": rec.source_level.name if rec.source_level else None,
                "target_level": rec.target_level.name if rec.target_level else None,
                "target_section": rec.target_section.name if rec.target_section else None,
                "target_academic_year": rec.target_academic_year or None,
                "reason": rec.reason or None,
                "date": rec.created_at.date().isoformat() if rec.created_at else None,
            }
    return None


def get_student_remarks(student_id, academic_year):
    """
    Returns remarks entered for the student in this academic year
    (from exam marks or academic records).
    """
    from .models import ExamMark

    marks_with_remarks = (
        ExamMark.objects.filter(
            student_id=student_id,
            exam_schedule__academic_year=academic_year,
        )
        .exclude(remarks="")
        .select_related("exam_schedule__subject", "exam_schedule__examination")
    )

    remarks_list = []
    for mark in marks_with_remarks:
        remarks_list.append({
            "subject": mark.exam_schedule.subject.name,
            "examination": mark.exam_schedule.examination.name,
            "remarks": mark.remarks,
        })
    return remarks_list


def sort_academic_years(year_strings):
    """
    Sorts academic year strings chronologically using academics.AcademicYear.start_date
    with fallback to numeric/lexical sorting.
    """
    from academics.models import AcademicYear
    import re

    years_list = list(set(year_strings))
    ay_map = {ay.name: ay.start_date for ay in AcademicYear.objects.filter(name__in=years_list)}

    def sort_key(y_str):
        if y_str in ay_map and ay_map[y_str]:
            return (0, ay_map[y_str].isoformat())
        match = re.search(r"\d{4}", y_str)
        if match:
            return (1, f"{int(match.group(0)):04d}_{y_str}")
        return (2, y_str)

    return sorted(years_list, key=sort_key)


def user_can_access_student_report(request, student):
    """
    Object-level authorization for Student Report Card and Academic Transcript:
    - Superuser / Owner: True
    - Student: True if viewing their own record
    - Parent: True if caller has parent record linked to this student AND has 'view_child_results' permission
    - Staff: Requires 'view_results' permission. If instructor, requires teaching assignment for one of student's sections.
    """
    if is_owner(request):
        return True

    own_student = get_student_for_user(request.user)
    if own_student is not None:
        return own_student.id == student.id

    from parent_portal.services import get_child_for_parent, get_parent_for_user
    parent = get_parent_for_user(request.user)
    if parent is not None:
        from roles.permissions import HasPermission
        if not HasPermission("view_child_results").has_permission(request, None):
            return False
        return get_child_for_parent(parent, student.id) is not None

    from roles.permissions import HasPermission
    if not HasPermission("view_results").has_permission(request, None):
        return False

    return user_can_access_student_result(request, student)


def get_student_co_scholastic_summary(student_id, academic_year=None):
    """
    Returns co-scholastic grades for a student across all activities and examinations in an academic year.
    """
    from .models import CoScholasticGrade

    qs = CoScholasticGrade.objects.filter(student_id=student_id).select_related(
        "activity", "examination"
    )
    if academic_year:
        qs = qs.filter(examination__academic_year=academic_year)
    qs = qs.order_by("examination__start_date", "activity__order", "activity__name")

    results = []
    for g in qs:
        results.append(
            {
                "id": str(g.id),
                "activity_id": str(g.activity_id),
                "activity_name": g.activity.name,
                "activity_code": g.activity.code,
                "grade": g.grade,
                "remarks": g.remarks,
                "examination_id": str(g.examination_id),
                "examination_name": g.examination.name,
            }
        )
    return results


def get_student_term_weightage_summary(student_id, academic_year, level_id=None):
    """
    Consolidates multiple published examination results for a student according
    to the configured TermWeightage rules for their class level and academic year.
    """
    from .models import ExamResult, GradeBoundary, TermWeightage

    if not level_id:
        return {"is_configured": False, "examinations": [], "subjects": [], "overall": None}

    weightages = list(
        TermWeightage.objects.filter(
            academic_year=academic_year, level_id=level_id
        ).select_related("examination")
    )
    if not weightages:
        return {"is_configured": False, "examinations": [], "subjects": [], "overall": None}

    total_weightage = sum(w.weightage_percentage for w in weightages)

    exam_ids = [w.examination_id for w in weightages]
    results = {
        r.examination_id: r
        for r in ExamResult.objects.filter(
            student_id=student_id, academic_year=academic_year, examination_id__in=exam_ids
        )
    }

    boundaries = list(
        GradeBoundary.objects.filter(academic_year=academic_year).order_by("-min_percentage")
    )

    def grade_for(pct):
        if pct is None:
            return None
        exact = Decimal(str(pct))
        for b in boundaries:
            if b.min_percentage <= exact <= b.max_percentage:
                return b.grade_label
        return None

    subject_map = {}
    exam_info_list = []
    for w in weightages:
        exam = w.examination
        w_pct = float(w.weightage_percentage)
        exam_info_list.append(
            {
                "examination_id": str(exam.id),
                "examination_name": exam.name,
                "weightage_percentage": w_pct,
                "is_published": exam.id in results,
            }
        )
        res = results.get(exam.id)
        if not res:
            continue
        for sub in res.subject_breakdown:
            sub_id = sub.get("subject")
            if not sub_id:
                continue
            if sub_id not in subject_map:
                subject_map[sub_id] = {
                    "subject_id": sub_id,
                    "subject_name": sub.get("subject_name", ""),
                    "terms": [],
                }
            s_pct = sub.get("percentage")
            weighted_pct = round((s_pct * w_pct) / 100.0, 2) if s_pct is not None else None
            subject_map[sub_id]["terms"].append(
                {
                    "examination_id": str(exam.id),
                    "examination_name": exam.name,
                    "weightage": w_pct,
                    "percentage": s_pct,
                    "weighted_percentage": weighted_pct,
                    "is_pass": sub.get("is_pass", False),
                }
            )

    subjects_summary = []
    overall_weighted_sums = []

    for sub_id, data in subject_map.items():
        valid_terms = [t for t in data["terms"] if t["weighted_percentage"] is not None]
        if valid_terms:
            sub_weightage_sum = sum(t["weightage"] for t in valid_terms)
            weighted_total = sum(t["weighted_percentage"] for t in valid_terms)
            consolidated_pct = (
                round((weighted_total / sub_weightage_sum) * 100.0, 2)
                if sub_weightage_sum > 0
                else 0.0
            )
            grade = grade_for(consolidated_pct)
            is_pass = all(t["is_pass"] for t in valid_terms) and consolidated_pct >= 33.0
            subjects_summary.append(
                {
                    "subject_id": sub_id,
                    "subject_name": data["subject_name"],
                    "terms": data["terms"],
                    "consolidated_percentage": consolidated_pct,
                    "consolidated_grade": grade,
                    "is_pass": is_pass,
                }
            )
            overall_weighted_sums.append(consolidated_pct)

    overall_pct = (
        round(sum(overall_weighted_sums) / len(overall_weighted_sums), 2)
        if overall_weighted_sums
        else None
    )
    overall_grade = grade_for(overall_pct)

    return {
        "is_configured": True,
        "total_weightage_configured": float(total_weightage),
        "examinations": exam_info_list,
        "subjects": subjects_summary,
        "overall": {
            "percentage": overall_pct,
            "grade": overall_grade,
        },
    }


def build_student_report_card(student, academic_year=None):
    """
    Builds the complete single-student, single-academic-year Report Card payload.
    Never recalculates published ExamResult snapshots.
    """
    from django.utils import timezone
    from academics.models import Subject
    from .models import ExamResult, GradeBoundary

    # Resolve academic year if not provided
    if not academic_year:
        current_enrollment = student.enrollments.filter(is_current=True).first()
        if current_enrollment:
            academic_year = current_enrollment.academic_year
        else:
            latest_result = ExamResult.objects.filter(student=student).order_by("-published_at").first()
            academic_year = latest_result.academic_year if latest_result else "Current"

    enrollment = student.enrollments.filter(academic_year=academic_year).select_related("level", "section").first()
    if not enrollment:
        enrollment = student.enrollments.filter(is_current=True).select_related("level", "section").first()

    results_qs = (
        ExamResult.objects.filter(student=student, academic_year=academic_year)
        .select_related("examination", "examination__exam_type")
        .order_by("examination__start_date")
    )

    boundaries = list(GradeBoundary.objects.filter(academic_year=academic_year).order_by("-min_percentage"))
    has_gp = bool(boundaries) and not any(b.grade_point is None for b in boundaries)

    # Pre-fetch all referenced subjects for credits
    all_subject_ids = set()
    for res in results_qs:
        for item in res.subject_breakdown:
            if item.get("subject"):
                all_subject_ids.add(item["subject"])
    subjects_map = {
        str(sub.id): sub
        for sub in Subject.objects.filter(id__in=all_subject_ids)
    }

    examinations_data = []
    total_obtained_sum = Decimal("0")
    total_max_sum = Decimal("0")
    exam_gpas = []

    for res in results_qs:
        enriched_breakdown = []
        for item in res.subject_breakdown:
            sub_id = str(item.get("subject", ""))
            sub_obj = subjects_map.get(sub_id)
            credits = float(sub_obj.credits) if sub_obj and sub_obj.credits is not None else 1.0

            grade_point = None
            if has_gp and item.get("grade"):
                for b in boundaries:
                    if b.grade_label == item.get("grade"):
                        grade_point = float(b.grade_point)
                        break

            enriched_breakdown.append({
                **item,
                "credits": credits,
                "grade_point": grade_point,
            })

        exam_gpa = calculate_gpa(res.subject_breakdown, academic_year)
        if exam_gpa is not None:
            exam_gpas.append(exam_gpa)

        total_obtained_sum += res.total_marks_obtained
        total_max_sum += res.total_max_marks

        examinations_data.append({
            "id": str(res.id),
            "examination": str(res.examination_id),
            "examination_name": res.examination.name,
            "exam_type": res.examination.exam_type.name if res.examination.exam_type else "",
            "academic_year": res.academic_year,
            "total_marks_obtained": float(res.total_marks_obtained),
            "total_max_marks": float(res.total_max_marks),
            "percentage": float(res.percentage),
            "overall_grade": res.overall_grade,
            "is_pass": res.is_pass,
            "gpa": exam_gpa,
            "subject_breakdown": enriched_breakdown,
            "published_at": res.published_at.isoformat() if res.published_at else None,
        })

    overall_percentage = (
        round(float(total_obtained_sum / total_max_sum) * 100, 2)
        if total_max_sum > 0
        else None
    )
    overall_grade = None
    if overall_percentage is not None:
        exact_pct = Decimal(str(overall_percentage))
        for b in boundaries:
            if b.min_percentage <= exact_pct <= b.max_percentage:
                overall_grade = b.grade_label
                break

    overall_gpa = None
    if has_gp and exam_gpas and len(exam_gpas) == len(examinations_data):
        overall_gpa = round(sum(exam_gpas) / len(exam_gpas), 2)

    all_passed = bool(examinations_data) and all(e["is_pass"] for e in examinations_data)

    attendance = get_student_attendance_summary(student.id, academic_year)
    promotion = get_student_promotion_summary(student.id, academic_year)
    remarks = get_student_remarks(student.id, academic_year)
    institution = get_institution_summary()
    co_scholastic = get_student_co_scholastic_summary(student.id, academic_year=academic_year)
    term_weightage = get_student_term_weightage_summary(
        student.id,
        academic_year=academic_year,
        level_id=enrollment.level_id if enrollment else None,
    )

    return {
        "institution": institution,
        "student": {
            "id": str(student.id),
            "full_name": f"{student.profile.first_name} {student.profile.last_name}",
            "enrollment_id": student.enrollment_id,
            "date_of_birth": student.profile.date_of_birth.isoformat() if student.profile.date_of_birth else None,
            "gender": student.profile.gender or None,
            "level": enrollment.level.name if enrollment and enrollment.level else None,
            "section": enrollment.section.name if enrollment and enrollment.section else None,
            "status": student.status,
        },
        "academic_year": academic_year,
        "examinations": examinations_data,
        "summary": {
            "total_marks_obtained": float(total_obtained_sum),
            "total_max_marks": float(total_max_sum),
            "percentage": overall_percentage,
            "overall_grade": overall_grade,
            "gpa": overall_gpa,
            "is_pass": all_passed,
            "total_exams": len(examinations_data),
        },
        "attendance": attendance,
        "promotion": promotion,
        "remarks": remarks,
        "co_scholastic": co_scholastic,
        "term_weightage": term_weightage,
        "generated_at": timezone.now().isoformat(),
    }


def build_student_transcript(student):
    """
    Builds the official multi-year Academic Transcript across all eligible
    academic years where student has enrollments or published results.
    Chronologically ordered from earliest to latest.
    """
    from django.utils import timezone
    from .models import ExamResult

    enrollment_years = list(student.enrollments.values_list("academic_year", flat=True))
    result_years = list(ExamResult.objects.filter(student=student).values_list("academic_year", flat=True))
    all_years = list(set(enrollment_years + result_years))
    sorted_years = sort_academic_years(all_years)

    years_data = []
    total_obtained_all = Decimal("0")
    total_max_all = Decimal("0")
    total_credits_attempted = 0.0
    total_credits_earned = 0.0
    valid_year_gpas = []

    for year in sorted_years:
        report = build_student_report_card(student, academic_year=year)
        summary = report["summary"]
        examinations = report["examinations"]
        enrollment_info = report["student"]
        attendance = report["attendance"]
        promotion = report["promotion"]

        # Track credits
        for exam in examinations:
            for sub in exam.get("subject_breakdown", []):
                cr = float(sub.get("credits", 1.0) or 1.0)
                total_credits_attempted += cr
                if sub.get("is_pass"):
                    total_credits_earned += cr

        total_obtained_all += Decimal(str(summary["total_marks_obtained"]))
        total_max_all += Decimal(str(summary["total_max_marks"]))
        if summary.get("gpa") is not None:
            valid_year_gpas.append(summary["gpa"])

        years_data.append({
            "academic_year": year,
            "level": enrollment_info.get("level"),
            "section": enrollment_info.get("section"),
            "examinations": examinations,
            "summary": summary,
            "attendance": attendance,
            "promotion": promotion,
        })

    cumulative_percentage = (
        round(float(total_obtained_all / total_max_all) * 100, 2)
        if total_max_all > 0
        else None
    )

    cgpa = (
        round(sum(valid_year_gpas) / len(valid_year_gpas), 2)
        if (valid_year_gpas and len(valid_year_gpas) == len(years_data))
        else None
    )

    institution = get_institution_summary()

    return {
        "institution": institution,
        "student": {
            "id": str(student.id),
            "full_name": f"{student.profile.first_name} {student.profile.last_name}",
            "enrollment_id": student.enrollment_id,
            "date_of_birth": student.profile.date_of_birth.isoformat() if student.profile.date_of_birth else None,
            "gender": student.profile.gender or None,
            "admission_date": student.admission_date.isoformat() if student.admission_date else None,
            "status": student.status,
        },
        "years": years_data,
        "cumulative_summary": {
            "total_marks_obtained": float(total_obtained_all),
            "total_max_marks": float(total_max_all),
            "cumulative_percentage": cumulative_percentage,
            "cgpa": cgpa,
            "total_credits_attempted": round(total_credits_attempted, 1),
            "total_credits_earned": round(total_credits_earned, 1),
            "total_years": len(years_data),
            "status": student.status,
        },
        "issuance": {
            "issued_date": timezone.localdate().isoformat(),
            "signatories": [
                {"title": "Class Teacher"},
                {"title": "Academic Coordinator"},
                {"title": "Principal / Head of Institution"},
            ],
        },
        "generated_at": timezone.now().isoformat(),
    }

