"""
Attendance business logic. Centralized here so percentage calculation and
section-level authorization are never re-implemented per view.
"""

from .models import DEFAULT_STATUS_WEIGHTS


def calculate_attendance_percentage(status_counts, settings):
    """
    status_counts: {"present": 25, "absent": 3, "late": 4, "half_day": 5, "leave": 3}
    settings: an AttendanceSettings instance.

    Returns a float percentage (0-100), or None if every counted status has a
    null weight (nothing left in the denominator - e.g. a day that was 100% leave).
    """
    weights = settings.status_weights or {}
    numerator = 0.0
    denominator = 0

    for status_key, count in status_counts.items():
        if not count:
            continue
        weight = weights.get(status_key, DEFAULT_STATUS_WEIGHTS.get(status_key))
        if weight is None:
            continue
        numerator += float(weight) * count
        denominator += count

    if denominator == 0:
        return None
    return round((numerator / denominator) * 100, 2)


def get_section_roster(section_id):
    """
    The current roster for a section - i.e. who attendance should be marked
    for today. Never Student.objects.all(); always via the current
    StudentLevel enrollment, matching the pattern already used in
    course_content._get_targeted_students().
    """
    from students.models import Student

    return (
        Student.objects.filter(
            enrollments__section_id=section_id,
            enrollments__is_current=True,
            status="active",
        )
        .select_related("profile")
        .distinct()
    )


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


def user_can_access_section(request, section_id):
    """
    Object-level authorization for a specific Section's attendance.

    - Owner (or superuser) bypasses, matching the existing HasPermission
      owner-bypass convention used everywhere else in the project.
    - A user who has an Instructor record is scoped to sections where they
      hold a SubjectAssignment - this is the rule explicitly required for
      instructors, and is checked regardless of which Role granted their
      attendance permission.
    - A user with an attendance permission but no Instructor record (e.g. a
      non-teaching "staff" role, per its existing description "Non-teaching
      administrative staff") gets tenant-wide access, consistent with how
      every other module in this codebase already treats that role.

    A section that doesn't exist in the current tenant schema (including one
    belonging to a different tenant entirely) is always denied, regardless of
    role - it must never be possible for an owner-bypass or any other check
    to short-circuit past confirming the object actually exists here first.
    """
    from academics.models import Section

    if not Section.objects.filter(id=section_id).exists():
        return False

    if is_owner(request):
        return True

    instructor = get_instructor_for_user(request.user)
    if instructor is not None:
        from academics.models import SubjectAssignment

        return SubjectAssignment.objects.filter(
            section_id=section_id, instructor=instructor
        ).exists()

    return True


def user_can_access_student_attendance(request, student):
    """
    Object-level authorization for reading a specific Student's attendance
    history. A student may only ever read their own; anyone else needs the
    view_attendance permission (checked separately by the view) plus,
    if they're an instructor, section-scoping to at least one of that
    student's current sections.
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
