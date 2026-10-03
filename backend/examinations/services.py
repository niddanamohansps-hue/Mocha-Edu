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


def calculate_subject_result(exam_mark, exam_schedule):
    """
    Dynamic (pre-publication) per-subject result for one student, and also
    the shape snapshotted into ExamResult.subject_breakdown at publish time.
    """
    max_marks = exam_schedule.max_marks
    if exam_mark is None or exam_mark.is_absent:
        return {
            "subject": str(exam_schedule.subject_id),
            "subject_name": exam_schedule.subject.name,
            "marks_obtained": None,
            "max_marks": float(max_marks),
            "percentage": None,
            "grade": None,
            "is_absent": True,
            "is_pass": False,
        }

    if exam_mark.marks_obtained is None:
        return {
            "subject": str(exam_schedule.subject_id),
            "subject_name": exam_schedule.subject.name,
            "marks_obtained": None,
            "max_marks": float(max_marks),
            "percentage": None,
            "grade": None,
            "is_absent": False,
            "is_pass": False,
        }

    percentage = round(float(exam_mark.marks_obtained / max_marks) * 100, 2)
    grade_label, _ = calculate_grade(percentage, exam_schedule.academic_year)
    return {
        "subject": str(exam_schedule.subject_id),
        "subject_name": exam_schedule.subject.name,
        "marks_obtained": float(exam_mark.marks_obtained),
        "max_marks": float(max_marks),
        "percentage": percentage,
        "grade": grade_label,
        "is_absent": False,
        "is_pass": exam_mark.marks_obtained >= exam_schedule.pass_marks,
    }


def calculate_student_examination_result(examination, student):
    """
    Equal-weighted aggregate across every ExamSchedule of this examination
    that the student has a mark row for (schedules with no mark at all for
    this student are treated as not-applicable, not as a zero - e.g. the
    student wasn't enrolled in that subject).
    """
    from .models import ExamMark, ExamSchedule

    schedules = ExamSchedule.objects.filter(examination=examination).select_related("subject")
    marks_by_schedule = {
        m.exam_schedule_id: m
        for m in ExamMark.objects.filter(exam_schedule__examination=examination, student=student)
    }

    breakdown = []
    total_obtained = Decimal("0")
    total_max = Decimal("0")
    any_fail = False
    participated = False

    for schedule in schedules:
        mark = marks_by_schedule.get(schedule.id)
        if mark is None:
            continue
        participated = True
        subject_result = calculate_subject_result(mark, schedule)
        breakdown.append(subject_result)

        if subject_result["is_absent"] or subject_result["marks_obtained"] is None:
            any_fail = True
            total_max += schedule.max_marks
            continue

        total_obtained += mark.marks_obtained
        total_max += schedule.max_marks
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
        published_student_ids = []
        for student in Student.objects.filter(id__in=student_ids):
            result = calculate_student_examination_result(examination, student)
            if result is None:
                continue
            ExamResult.objects.create(
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
            published_student_ids.append(student.id)

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
