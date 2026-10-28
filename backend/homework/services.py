"""
Who may do what with homework, and the notices it sends.

- Setting homework (manage_homework): a teacher only for a section and subject they are assigned to; staff
  without a teaching record, and the owner, for any section (the rule attendance already uses).
- Seeing it: the same staff; a student for their own current section; a parent for a linked child's section.
- Marking seen / done: the student, or a parent for that child.
"""
from django.db import transaction
from django.utils import timezone

from attendance.services import get_instructor_for_user, get_staff_member_for_user, get_student_for_user, is_owner


def can_set_for(request, section_id, subject_id):
    from academics.models import Section, Subject, SubjectAssignment

    if not Section.objects.filter(id=section_id).exists() or not Subject.objects.filter(id=subject_id).exists():
        return False
    if is_owner(request):
        return True
    instructor = get_instructor_for_user(request.user)
    if instructor is None:
        return True  # non-teaching staff with manage_homework: school-wide, as in attendance
    return SubjectAssignment.objects.filter(section_id=section_id, subject_id=subject_id, instructor=instructor).exists()


def staff_sections(request):
    """Section ids a teacher may see, or None for no limit (owner and non-teaching staff)."""
    from academics.models import SubjectAssignment

    if is_owner(request):
        return None
    instructor = get_instructor_for_user(request.user)
    if instructor is None:
        return None
    return set(SubjectAssignment.objects.filter(instructor=instructor).values_list("section_id", flat=True))


def current_section_id(student):
    level = student.enrollments.filter(is_current=True).only("section_id").first()
    return level.section_id if level else None


def student_for_request(request, student_id=None):
    """The student whose homework this user may see and mark: themselves, or a linked child. None otherwise."""
    if student_id:
        from parent_portal.services import get_child_for_parent, get_parent_for_user

        parent = get_parent_for_user(request.user)
        if parent is not None:
            return get_child_for_parent(parent, student_id)
        own = get_student_for_user(request.user)
        return own if own and str(own.id) == str(student_id) else None
    return get_student_for_user(request.user)


def mark(homework, student, *, seen=False, done=None):
    from .models import HomeworkProgress

    with transaction.atomic():
        progress, _ = HomeworkProgress.objects.select_for_update().get_or_create(homework=homework, student=student)
        now = timezone.now()
        if seen and not progress.seen_at:
            progress.seen_at = now
        if done is not None:
            progress.done_at = now if done else None
            if done and not progress.seen_at:
                progress.seen_at = now
        progress.save()
    return progress


def recipients_for_section(section_id):
    """User ids of students in the section (with a login) and of their parents (with a login)."""
    from families.models import StudentParentRelation
    from students.models import StudentLevel

    student_ids = list(StudentLevel.objects.filter(section_id=section_id, is_current=True, student__status="active")
                       .values_list("student_id", flat=True))
    users = set(StudentLevel.objects.filter(student_id__in=student_ids, is_current=True)
                .exclude(student__profile__user_id=None).values_list("student__profile__user_id", flat=True))
    users |= set(StudentParentRelation.objects.filter(student_id__in=student_ids)
                 .exclude(parent__profile__user_id=None).values_list("parent__profile__user_id", flat=True))
    return [u for u in users if u]


def notify_new_homework(homework):
    from notifications.services import notify_many

    users = recipients_for_section(homework.section_id)
    if users:
        notify_many(
            recipient_user_ids=users,
            title=f"New homework: {homework.subject.name}",
            body=f"{homework.title}. Due {homework.due_date:%d %b %Y}.",
            category="homework",
            link="/dashboard/homework",
        )
    return len(users)


def created_by_for(request):
    return get_staff_member_for_user(request.user)
