"""
Parent-specific authorization. Deliberately independent from
attendance/timetable/examinations' object-level authorization - those
modules fall through to tenant-wide access for any permission-holder who
isn't the student themself, the owner, or a section-scoped instructor
(see attendance.services.user_can_access_student_attendance and
examinations.services.user_can_access_student_result). That fallback is
correct for a non-teaching "staff" role but would be a severe IDOR if
reused for parents, so this module never imports or calls it, and there
is deliberately NO owner-bypass here either - a parent's access is ALWAYS
scoped through families.StudentParentRelation, with no "everyone else"
fallback of any kind.
"""


def get_profile_for_user(user):
    from profiles.models import Profile

    if not user or not getattr(user, "is_authenticated", False):
        return None
    return Profile.objects.filter(user_id=user.id).first()


def get_parent_for_user(user):
    """
    Resolves the Parent record for the authenticated user via the same
    Profile soft-link every other identity helper in this codebase uses -
    Profile.parent_record is the reverse of Parent.profile, the exact same
    OneToOne pattern as student_record/staff_record.
    """
    profile = get_profile_for_user(user)
    if not profile:
        return None
    return getattr(profile, "parent_record", None)


def get_linked_children(parent):
    """
    Every child currently linked to this parent, with the current
    enrollment (level/section) prefetched so the children list never
    N+1s per child.
    """
    from django.db.models import Prefetch

    from families.models import StudentParentRelation
    from students.models import StudentLevel

    current_enrollment_prefetch = Prefetch(
        "student__enrollments",
        queryset=StudentLevel.objects.filter(is_current=True).select_related(
            "level", "section"
        ),
        to_attr="current_enrollment_list",
    )
    return (
        StudentParentRelation.objects.filter(parent=parent)
        .select_related("student__profile")
        .prefetch_related(current_enrollment_prefetch)
        .order_by("student__profile__first_name")
    )


def get_child_for_parent(parent, student_id):
    """
    THE relationship-authority check. Returns the Student instance if, and
    only if, a StudentParentRelation links this exact parent to this exact
    student_id right now - never trusts the URL's student_id beyond this.

    Returns None for both "student doesn't exist" and "student exists but
    isn't linked to this parent" - the two cases are deliberately
    indistinguishable to the caller, so a denial response can never be used
    to enumerate whether some other parent's child exists.
    """
    from families.models import StudentParentRelation

    relation = (
        StudentParentRelation.objects.filter(parent=parent, student_id=student_id)
        .select_related("student__profile")
        .first()
    )
    return relation.student if relation else None


def user_can_access_child(user, student_id):
    """
    Convenience boolean wrapper around get_child_for_parent, for callers
    that only need a yes/no answer (e.g. tests exercising the
    authorization rule directly rather than through a view).
    """
    parent = get_parent_for_user(user)
    if parent is None:
        return False
    return get_child_for_parent(parent, student_id) is not None
