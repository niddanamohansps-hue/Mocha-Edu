from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
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
)
from students.models import Student
from roles.permissions import HasPermission


def can_student_access_content(student, content):
    """
    Check if a student can access specific content based on targeting
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
        if self.action in ["list", "retrieve"]:
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
            accessible_ids = [
                content.id
                for content in queryset
                if can_student_access_content(student, content)
            ]
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


class SubjectEnrollmentViewSet(viewsets.ModelViewSet):
    queryset = SubjectEnrollment.objects.all().select_related(
        "student__profile", "subject__level"
    )
    serializer_class = SubjectEnrollmentSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["student", "subject", "academic_year"]

    def get_permissions(self):
        if self.action in ["list", "retrieve"]:
            return [permissions.IsAuthenticated()]
        return [
            permissions.IsAuthenticated(),
            HasPermission("manage_subject_enrollment"),
        ]

    @action(detail=False, methods=["post"])
    def bulk_enroll(self, request):
        """
        Enroll multiple students in a subject
        Payload: {
            "subject_id": "uuid",
            "student_ids": ["uuid1", "uuid2"],
            "academic_year": "2081"
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

        created_count = 0
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
            accessible_content_ids = [
                content.id
                for content in CourseContent.objects.filter(
                    content_type="assignment", is_published=True
                )
                if can_student_access_content(student, content)
            ]
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


class AssignmentSubmissionViewSet(viewsets.ModelViewSet):
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
        if self.action == "submit":
            return [permissions.IsAuthenticated(), HasPermission("submit_assignment")]
        if self.action in ["grade", "bulk_grade"]:
            return [permissions.IsAuthenticated(), HasPermission("grade_assignment")]
        return [permissions.IsAuthenticated()]

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user

        # Students only see their own submissions
        from profiles.models import Profile

        profile = Profile.objects.filter(user_id=user.id).first()
        if profile and hasattr(profile, "student_record"):
            student = profile.student_record
            queryset = queryset.filter(student=student)

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

        # Update submission
        submission.submission_file = request.data.get("submission_file")
        submission.submission_text = request.data.get("submission_text", "")
        submission.submission_url = request.data.get("submission_url", "")
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

        score = request.data.get("score")
        feedback = request.data.get("feedback", "")

        if score is None:
            return Response(
                {"error": "Score is required"}, status=status.HTTP_400_BAD_REQUEST
            )

        submission.score = score
        submission.feedback = feedback
        submission.graded_by = staff_member
        submission.graded_at = timezone.now()
        submission.status = "graded"
        submission.save()

        serializer = self.get_serializer(submission)
        return Response(serializer.data)
