"""
Timetable business logic and object-level authorization. Centralized here so
these rules are never re-implemented per view or serializer, mirroring the
exact pattern established in attendance/services.py.
"""

from rest_framework import serializers


# --- Identity resolution -----------------------------------------------
# Duplicated from attendance/services.py rather than imported cross-app -
# Timetable and Attendance are peer TENANT_APPS and neither should depend on
# the other. If a third module needs the same helpers, consolidate into
# core at that point (not before - two consumers doesn't justify it yet).

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

def user_can_access_section(request, section_id):
    """
    - Owner bypasses.
    - An Instructor-record holder is scoped to sections where they hold a
      SubjectAssignment (same rule as attendance.services).
    - A student (this is the one deliberate difference from Attendance's
      version of this function: Attendance never exposes its section-scoped
      endpoint to students directly, but Timetable's IS reachable by
      students, since viewing your own section's timetable is a core
      requirement here) is scoped to their own current section only.
    - Everyone else with the relevant permission gets tenant-wide access.

    A section that doesn't exist in the current schema (including one
    belonging to a different tenant) is always denied.
    """
    from academics.models import Section, SubjectAssignment

    if not Section.objects.filter(id=section_id).exists():
        return False

    if is_owner(request):
        return True

    instructor = get_instructor_for_user(request.user)
    if instructor is not None:
        return SubjectAssignment.objects.filter(
            section_id=section_id, instructor=instructor
        ).exists()

    student = get_student_for_user(request.user)
    if student is not None:
        return student.enrollments.filter(is_current=True, section_id=section_id).exists()

    return True


def user_can_access_instructor_timetable(request, instructor_id):
    """
    An instructor may always view their own timetable. Anyone else needs
    view_timetable (checked by the view) - a student may never use this
    endpoint to inspect an arbitrary instructor's schedule.
    """
    own_instructor = get_instructor_for_user(request.user)
    if own_instructor is not None:
        return str(own_instructor.id) == str(instructor_id)

    if is_owner(request):
        return True

    if get_student_for_user(request.user) is not None:
        return False

    return True


# --- Business validation --------------------------------------------------

def validate_timetable_entry(*, section, subject, period, academic_year, instructor):
    """
    Runs every "before create/update" rule required by the spec. Raises
    serializers.ValidationError with a clear, field-scoped message - never
    lets an inconsistent entry reach the database in the first place.
    """
    if period.academic_year != academic_year:
        raise serializers.ValidationError(
            {"period": "Selected period does not belong to this timetable entry's academic year."}
        )

    if period.is_break:
        raise serializers.ValidationError(
            {"period": "Selected period is a break and cannot contain a subject."}
        )

    if subject.level_id != section.level_id:
        raise serializers.ValidationError(
            {"subject": "Selected subject does not belong to this section's academic level."}
        )

    if instructor is not None:
        from academics.models import SubjectAssignment

        if not SubjectAssignment.objects.filter(
            section=section, subject=subject, instructor=instructor
        ).exists():
            raise serializers.ValidationError(
                {
                    "instructor": (
                        "Selected instructor is not assigned to this subject for this section."
                    )
                }
            )


def check_entry_conflicts(*, section, instructor, room, academic_year, day_of_week, period, exclude_id=None):
    """
    Proactively checks all three conflict rules BEFORE attempting a write, so
    the caller gets a clear, specific error rather than a raw IntegrityError.
    The database's own unique_together constraints remain the final
    protection against a race between two simultaneous requests.
    """
    from .models import TimetableEntry

    base_qs = TimetableEntry.objects.filter(academic_year=academic_year, day_of_week=day_of_week, period=period)
    if exclude_id:
        base_qs = base_qs.exclude(id=exclude_id)

    if base_qs.filter(section=section).exists():
        raise serializers.ValidationError(
            {"section": "This section already has a timetable entry for this period."}
        )

    if instructor is not None and base_qs.filter(instructor=instructor).exists():
        raise serializers.ValidationError(
            {"instructor": "This instructor is already scheduled during this period."}
        )

    if room is not None and base_qs.filter(room=room).exists():
        raise serializers.ValidationError(
            {"room": "This room is already occupied during this period."}
        )


def validate_substitution(*, timetable_entry, date, substitute_instructor):
    """
    Substitutions are per-date exceptions, so full date-based conflict
    checking across every other substitution on that date is out of scope
    for V1 (no TeacherAvailability model exists to resolve it generally).
    What CAN be safely determined from existing TimetableEntry data alone:
    is this substitute instructor already regularly scheduled elsewhere at
    this exact recurring day/period? That's an "obvious" conflict worth
    catching without inventing new infrastructure.
    """
    if substitute_instructor is None:
        return

    from .models import TimetableEntry

    conflicting = (
        TimetableEntry.objects.filter(
            academic_year=timetable_entry.academic_year,
            day_of_week=timetable_entry.day_of_week,
            period=timetable_entry.period,
            instructor=substitute_instructor,
        )
        .exclude(id=timetable_entry.id)
        .exists()
    )
    if conflicting:
        raise serializers.ValidationError(
            {
                "substitute_instructor": (
                    "This instructor is already regularly scheduled during this period "
                    "and cannot be assigned as a substitute."
                )
            }
        )
