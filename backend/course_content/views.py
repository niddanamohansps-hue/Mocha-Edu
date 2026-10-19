from rest_framework import mixins, viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from django.db.models import Q
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter

from core.pagination import StandardResultsPagination

from .models import CourseContent, SubjectEnrollment, Assignment, AssignmentSubmission
from .serializers import (
    CourseContentSerializer,
    SubjectEnrollmentSerializer,
    AssignmentSerializer,
    AssignmentSubmissionSerializer,
    CreateAssignmentSerializer,
    GradeSubmissionSerializer,
    SubmitAssignmentSerializer,
)
from students.models import Student
from roles.permissions import HasPermission
from accounts.tenant_access import HasAnyPermission, IsTenantMember


def _student_for_user(user):
    """The caller's own Student record (via the tenant Profile soft-link), or None."""
    from profiles.models import Profile

    profile = Profile.objects.filter(user_id=user.id).first()
    return getattr(profile, "student_record", None) if profile else None


def can_student_access_content(student, content):
    """
    Check if a student can access specific content based on targeting.

    Unbatched reference implementation: resolves the student's current
    enrollment and subject enrollments itself, and checks each targeting
    relation with its own `.filter(...).exists()` query. Safe to call for
    a single (student, content) pair. For checking MANY content items
    against the SAME student, use filter_content_accessible_to_student()
    below instead - it implements this exact same access rule without
    repeating the student-level lookups or issuing one query per
    targeting relation per content item (the confirmed N+1).
    """
    # Check explicit targeting
    if content.specific_students.filter(id=student.id).exists():
        return True

    # Get current enrollment
    current_enrollment = student.enrollments.filter(is_current=True).first()

    if current_enrollment:
        # Check section targeting
        if content.target_sections.filter(id=current_enrollment.section_id).exists():
            return True

        # Check level targeting
        if content.target_levels.filter(id=current_enrollment.level_id).exists():
            return True

        # Check program targeting
        if content.target_programs.filter(
            id=current_enrollment.level.program_id
        ).exists():
            return True

    # Check subject targeting
    student_subjects = student.subject_enrollments.values_list("subject_id", flat=True)
    if content.target_subjects.filter(id__in=student_subjects).exists():
        return True

    return False


def filter_content_accessible_to_student(student, queryset):
    """
    Applies the exact same access rule as can_student_access_content() to
    every item in `queryset`, for one student, without the N+1 that
    function has when called once per content item.

    The student-side inputs (current enrollment incl. level/section,
    and subject-enrollment ids) depend only on `student`, never on which
    content is being checked, so they're resolved ONCE for the whole
    batch instead of once per item. The content-side targeting relations
    (specific_students/target_sections/target_levels/target_programs/
    target_subjects) are prefetched in one query per relation (regardless
    of how many content items are in `queryset`), then checked by
    membership in Python instead of a fresh `.filter(...).exists()` call
    per item per relation.

    Returns a list of CourseContent ids - the same set
    can_student_access_content() would return True for, item by item.
    """
    content_list = list(
        queryset.prefetch_related(
            "specific_students",
            "target_sections",
            "target_levels",
            "target_programs",
            "target_subjects",
        )
    )
    if not content_list:
        return []

    current_enrollment = (
        student.enrollments.filter(is_current=True).select_related("level", "section").first()
    )
    # Matches can_student_access_content()'s current_enrollment.level.program_id
    # exactly, including its crash-on-level=None edge case (see Phase 9B
    # report) - not changed here, since fixing it is outside this phase's scope.
    current_program_id = current_enrollment.level.program_id if current_enrollment else None
    student_subject_ids = set(student.subject_enrollments.values_list("subject_id", flat=True))

    accessible_ids = []
    for content in content_list:
        if any(s.id == student.id for s in content.specific_students.all()):
            accessible_ids.append(content.id)
            continue

        if current_enrollment:
            if any(sec.id == current_enrollment.section_id for sec in content.target_sections.all()):
                accessible_ids.append(content.id)
                continue
            if any(lvl.id == current_enrollment.level_id for lvl in content.target_levels.all()):
                accessible_ids.append(content.id)
                continue
            if any(p.id == current_program_id for p in content.target_programs.all()):
                accessible_ids.append(content.id)
                continue

        if any(subj.id in student_subject_ids for subj in content.target_subjects.all()):
            accessible_ids.append(content.id)

    return accessible_ids


class CourseContentViewSet(viewsets.ModelViewSet):
    queryset = CourseContent.objects.all().select_related("created_by__profile")
    serializer_class = CourseContentSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["content_type", "is_published", "is_pinned", "created_by"]
    search_fields = ["title", "description"]
    ordering_fields = ["created_at", "updated_at", "publish_date"]
    ordering = ["-is_pinned", "-created_at"]
    pagination_class = StandardResultsPagination

    def get_permissions(self):
        if self.action in ["list", "retrieve", "download"]:
            return [permissions.IsAuthenticated(), HasPermission("view_course_content")]
        return [permissions.IsAuthenticated(), HasPermission("manage_course_content")]

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user

        # Support excluding assignments (for study materials page)
        exclude_assignments = (
            self.request.query_params.get("exclude_assignments", "").lower() == "true"
        )
        if exclude_assignments:
            queryset = queryset.exclude(content_type="assignment")

        # Students only see published content they have access to
        from profiles.models import Profile

        profile = Profile.objects.filter(user_id=user.id).first()
        if profile and hasattr(profile, "student_record"):
            student = profile.student_record
            queryset = queryset.filter(is_published=True)

            # Filter based on access control
            accessible_ids = filter_content_accessible_to_student(student, queryset)
            queryset = queryset.filter(id__in=accessible_ids)

        return queryset

    def perform_create(self, serializer):
        # Get staff member profile
        from profiles.models import Profile

        profile = Profile.objects.filter(user_id=self.request.user.id).first()
        if not profile or not hasattr(profile, "staff_record"):
            return Response(
                {"error": "Staff profile not found"},
                status=status.HTTP_403_FORBIDDEN,
            )
        staff_member = profile.staff_record
        serializer.save(
            created_by=staff_member,
            publish_date=(
                timezone.now()
                if serializer.validated_data.get("is_published")
                else None
            ),
        )

    @action(detail=False, methods=["get"])
    def my_content(self, request):
        """Get content created by the current staff member (excluding assignments)"""
        from profiles.models import Profile

        profile = Profile.objects.filter(user_id=request.user.id).first()
        if not profile or not hasattr(profile, "staff_record"):
            return Response(
                {"error": "Staff profile not found"},
                status=status.HTTP_403_FORBIDDEN,
            )
        staff_member = profile.staff_record

        # Exclude assignments - they have their own dedicated page
        content = self.queryset.filter(created_by=staff_member).exclude(
            content_type="assignment"
        )

        page = self.paginate_queryset(content)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(content, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["get"])
    def download(self, request, pk=None):
        content = self.get_object()
        if not content.file:
            return Response(
                {"error": "No file attached to this content."},
                status=status.HTTP_404_NOT_FOUND,
            )

        user = request.user
        authorized = False

        if getattr(user, "is_superuser", False):
            authorized = True
        else:
            from roles.permissions import HasPermission
            if (
                HasPermission("view_course_content").has_permission(request, self)
                or HasPermission("manage_course_content").has_permission(request, self)
            ):
                authorized = True
            else:
                from profiles.models import Profile
                profile = Profile.objects.filter(user_id=user.id).first()
                if profile and hasattr(profile, "student_record"):
                    student = profile.student_record
                    if content.is_published and can_student_access_content(student, content):
                        authorized = True

        if not authorized:
            return Response(
                {"error": "You do not have permission to download this file."},
                status=status.HTTP_403_FORBIDDEN,
            )

        from django.http import FileResponse
        return FileResponse(content.file.open("rb"), as_attachment=True)


class SubjectEnrollmentViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    # Enrollment rows are immutable (student, subject, year): no PUT/PATCH. Remove and re-create instead.
    queryset = SubjectEnrollment.objects.all().select_related(
        "student__profile", "subject__level"
    )
    serializer_class = SubjectEnrollmentSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["student", "subject", "academic_year"]

    def get_permissions(self):
        if self.action in ["list", "retrieve"]:
            return [permissions.IsAuthenticated(), IsTenantMember()]
        return [
            permissions.IsAuthenticated(),
            IsTenantMember(),
            HasPermission("manage_subject_enrollment"),
        ]

    def get_queryset(self):
        queryset = super().get_queryset()
        if self.action in ["list", "retrieve"]:
            # A student reads only their own enrollments; managers read all; nobody else reads any.
            student = _student_for_user(self.request.user)
            if student is not None:
                return queryset.filter(student=student)
            if not HasPermission("manage_subject_enrollment").has_permission(
                self.request, self
            ):
                raise PermissionDenied(
                    "You do not have permission to view subject enrollments."
                )
        return queryset

    @action(detail=False, methods=["post"])
    def bulk_enroll(self, request):
        """
        Enroll multiple students in a subject
        Payload: {
            "subject_id": "uuid",
            "student_ids": ["uuid1", "uuid2"],
            "academic_year": "2026-27"
        }
        """
        subject_id = request.data.get("subject_id")
        student_ids = request.data.get("student_ids", [])
        academic_year = request.data.get("academic_year")

        if not all([subject_id, student_ids, academic_year]):
            return Response(
                {"error": "subject_id, student_ids, and academic_year are required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        from django.db import transaction
        from students.models import StudentLevel

        known_years = set(StudentLevel.objects.values_list("academic_year", flat=True).distinct())
        if academic_year not in known_years:
            return Response(
                {"error": f"Unknown academic year '{academic_year}'. Use a year that exists for this school."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        created_count = 0
        with transaction.atomic():
            for student_id in student_ids:
                _, created = SubjectEnrollment.objects.get_or_create(
                    student_id=student_id,
                    subject_id=subject_id,
                    academic_year=academic_year,
                )
                if created:
                    created_count += 1

        return Response(
            {
                "message": f"Enrolled {created_count} students",
                "total_requested": len(student_ids),
                "newly_enrolled": created_count,
            }
        )


class AssignmentViewSet(viewsets.ModelViewSet):
    queryset = Assignment.objects.all().select_related("content__created_by__profile")
    serializer_class = AssignmentSerializer
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ["submission_type", "allow_late_submission"]
    ordering_fields = ["due_date", "total_points"]
    ordering = ["due_date"]
    pagination_class = StandardResultsPagination

    def get_permissions(self):
        if self.action in ["list", "retrieve"]:
            return [permissions.IsAuthenticated(), HasPermission("view_course_content")]
        if self.action == "create":
            return [permissions.IsAuthenticated(), HasPermission("create_assignment")]
        return [permissions.IsAuthenticated(), HasPermission("grade_assignment")]

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user

        # Students only see assignments for content they can access
        from profiles.models import Profile

        profile = Profile.objects.filter(user_id=user.id).first()
        if profile and hasattr(profile, "student_record"):
            student = profile.student_record
            accessible_content_ids = filter_content_accessible_to_student(
                student,
                CourseContent.objects.filter(content_type="assignment", is_published=True),
            )
            queryset = queryset.filter(content_id__in=accessible_content_ids)

        return queryset

    def create(self, request, *args, **kwargs):
        """
        Create assignment with content and auto-create pending submissions
        """
        serializer = CreateAssignmentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        from profiles.models import Profile

        profile = Profile.objects.filter(user_id=request.user.id).first()
        if not profile or not hasattr(profile, "staff_record"):
            return Response(
                {"error": "Staff profile not found"},
                status=status.HTTP_403_FORBIDDEN,
            )
        staff_member = profile.staff_record

        # Create CourseContent
        content = CourseContent.objects.create(
            title=serializer.validated_data["title"],
            description=serializer.validated_data["description"],
            content_type="assignment",
            file=serializer.validated_data.get("file"),
            external_url=serializer.validated_data.get("external_url", ""),
            created_by=staff_member,
            is_published=serializer.validated_data.get("is_published", True),
            is_pinned=serializer.validated_data.get("is_pinned", False),
            publish_date=(
                timezone.now()
                if serializer.validated_data.get("is_published")
                else None
            ),
        )

        # Set targets
        if serializer.validated_data.get("target_programs"):
            content.target_programs.set(serializer.validated_data["target_programs"])
        if serializer.validated_data.get("target_levels"):
            content.target_levels.set(serializer.validated_data["target_levels"])
        if serializer.validated_data.get("target_sections"):
            content.target_sections.set(serializer.validated_data["target_sections"])
        if serializer.validated_data.get("target_subjects"):
            content.target_subjects.set(serializer.validated_data["target_subjects"])
        if serializer.validated_data.get("specific_students"):
            content.specific_students.set(
                serializer.validated_data["specific_students"]
            )

        # Create Assignment
        assignment = Assignment.objects.create(
            content=content,
            due_date=serializer.validated_data["due_date"],
            total_points=serializer.validated_data.get("total_points", 100),
            submission_type=serializer.validated_data.get("submission_type", "file"),
            allow_late_submission=serializer.validated_data.get(
                "allow_late_submission", False
            ),
            late_penalty_percent=serializer.validated_data.get(
                "late_penalty_percent", 0
            ),
            instructions=serializer.validated_data["instructions"],
        )

        # Auto-create pending submissions for all targeted students
        targeted_students = self._get_targeted_students(content)
        for student in targeted_students:
            AssignmentSubmission.objects.create(
                assignment=assignment, student=student, status="pending"
            )

        response_serializer = AssignmentSerializer(assignment)
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)

    def _get_targeted_students(self, content):
        """Get all students targeted by the content"""
        students = Student.objects.none()

        # Specific students
        if content.specific_students.exists():
            students |= content.specific_students.all()

        # Program targeting
        if content.target_programs.exists():
            students |= Student.objects.filter(
                enrollments__level__program__in=content.target_programs.all(),
                enrollments__is_current=True,
            ).distinct()

        # Level targeting
        if content.target_levels.exists():
            students |= Student.objects.filter(
                enrollments__level__in=content.target_levels.all(),
                enrollments__is_current=True,
            ).distinct()

        # Section targeting
        if content.target_sections.exists():
            students |= Student.objects.filter(
                enrollments__section__in=content.target_sections.all(),
                enrollments__is_current=True,
            ).distinct()

        # Subject targeting
        if content.target_subjects.exists():
            students |= Student.objects.filter(
                subject_enrollments__subject__in=content.target_subjects.all()
            ).distinct()

        return students


class AssignmentSubmissionViewSet(
    mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet
):
    # Read-only resource plus the explicit submit / grade / download actions below. There is
    # deliberately no create, update or delete route: submissions are created when an
    # assignment is created, and changed only through submit (student) or grade (grader).
    queryset = AssignmentSubmission.objects.all().select_related(
        "assignment__content", "student__profile", "graded_by__profile"
    )
    serializer_class = AssignmentSubmissionSerializer
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ["assignment", "student", "status"]
    ordering_fields = ["submitted_at", "score"]
    ordering = ["-submitted_at"]
    pagination_class = StandardResultsPagination

    def get_permissions(self):
        # Every action requires tenant membership (the cookie-auth gate enforces it too).
        base = [permissions.IsAuthenticated(), IsTenantMember()]
        if self.action == "submit":
            return base + [HasPermission("submit_assignment")]
        if self.action == "grade":
            return base + [HasPermission("grade_assignment")]
        return base

    def get_queryset(self):
        queryset = super().get_queryset()

        # Students only ever reach their own submissions.
        student = _student_for_user(self.request.user)
        if student is not None:
            return queryset.filter(student=student)

        # Listing / reading submissions of other students needs a grading or course-management
        # permission. (submit / grade / download make their own object-level decisions below.)
        if self.action in ["list", "retrieve"] and not HasAnyPermission(
            "grade_assignment", "manage_course_content"
        ).has_permission(self.request, self):
            raise PermissionDenied("You do not have permission to view submissions.")

        return queryset

    @action(detail=True, methods=["post"])
    def submit(self, request, pk=None):
        """
        Submit an assignment
        """
        submission = self.get_object()

        # Verify it's the student's own submission
        if submission.student.profile.user_id != request.user.id:
            return Response(
                {"error": "You can only submit your own assignments"},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Work can be resubmitted until it is graded; a graded result is final here.
        if submission.status == "graded":
            return Response(
                {"error": "This submission has already been graded and can no longer be changed."},
                status=status.HTTP_409_CONFLICT,
            )

        # Only the submission fields are accepted (file size is validated here, on the real path).
        submit_serializer = SubmitAssignmentSerializer(data=request.data)
        submit_serializer.is_valid(raise_exception=True)
        data = submit_serializer.validated_data

        # Update submission
        submission.submission_file = data.get("submission_file")
        submission.submission_text = data.get("submission_text", "")
        submission.submission_url = data.get("submission_url", "")
        submission.submitted_at = timezone.now()
        submission.status = "submitted"
        submission.save()

        serializer = self.get_serializer(submission)
        return Response(serializer.data)

    @action(detail=True, methods=["post"])
    def grade(self, request, pk=None):
        """
        Grade a submission
        """
        submission = self.get_object()
        from profiles.models import Profile

        profile = Profile.objects.filter(user_id=request.user.id).first()
        if not profile or not hasattr(profile, "staff_record"):
            return Response(
                {"error": "Staff profile not found"},
                status=status.HTTP_403_FORBIDDEN,
            )
        staff_member = profile.staff_record

        if submission.status not in ("submitted", "graded"):
            return Response(
                {"error": "Only submitted work can be graded."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        grade_serializer = GradeSubmissionSerializer(
            data=request.data, context={"submission": submission}
        )
        grade_serializer.is_valid(raise_exception=True)

        submission.score = grade_serializer.validated_data["score"]
        submission.feedback = grade_serializer.validated_data.get("feedback", "")
        submission.graded_by = staff_member
        submission.graded_at = timezone.now()
        submission.status = "graded"
        submission.save()

        serializer = self.get_serializer(submission)
        return Response(serializer.data)

    @action(detail=True, methods=["get"])
    def download(self, request, pk=None):
        submission = self.get_object()
        if not submission.submission_file:
            return Response(
                {"error": "No file attached to this submission."},
                status=status.HTTP_404_NOT_FOUND,
            )

        user = request.user
        authorized = False

        if getattr(user, "is_superuser", False):
            authorized = True
        elif submission.student.profile and submission.student.profile.user_id == user.id:
            authorized = True
        else:
            from roles.permissions import HasPermission
            if (
                HasPermission("grade_assignment").has_permission(request, self)
                or HasPermission("manage_course_content").has_permission(request, self)
            ):
                authorized = True
            else:
                try:
                    from parent_portal.services import get_child_for_parent, get_parent_for_user
                    parent = get_parent_for_user(user)
                    if parent and get_child_for_parent(parent, submission.student_id):
                        authorized = True
                except Exception:
                    pass

        if not authorized:
            return Response(
                {"error": "You do not have permission to download this file."},
                status=status.HTTP_403_FORBIDDEN,
            )

        from django.http import FileResponse
        return FileResponse(submission.submission_file.open("rb"), as_attachment=True)
