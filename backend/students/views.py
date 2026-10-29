from academics.models import AcademicLevel
from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from django.db import transaction
from core.pagination import StandardResultsPagination
from roles.permissions import HasPermission
from .serializers import (
    PromotionBatchInputSerializer,
    PromotionRecordSerializer,
    StudentEnrollmentSerializer,
)
from .models import PromotionRecord, Student, StudentLevel
from .services import (
    execute_lifecycle_actions,
    get_exam_warnings_bulk,
    get_fee_warnings_bulk,
    get_next_level,
    get_promotion_candidates,
    get_staff_member_for_user,
    preview_lifecycle_actions,
    reverse_promotion,
)
from accounts.utils.crypto import decrypt_secret
from core.audit import log_action


class StudentEnrollmentView(APIView):
    """
    Unified endpoint for enrolling a new student.
    Handles profile creation, student record, and academic placement.
    """

    permission_classes = [IsAuthenticated, HasPermission("add_student")]

    def post(self, request):
        serializer = StudentEnrollmentSerializer(data=request.data)
        if serializer.is_valid():
            student = serializer.save()
            return Response(
                {
                    "message": "Student enrolled successfully",
                    "enrollment_id": student.enrollment_id,
                    "student_id": student.id,
                },
                status=status.HTTP_201_CREATED,
            )

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class StudentListView(APIView):
    """
    Paginated (StandardResultsPagination - page_size=20, max 100 via
    ?page_size=) directory of students. Ordered by name so pagination is
    deterministic across pages (previously unordered, which for a UUID
    primary key has no guaranteed stable order - a latent bug that only
    didn't matter while every row was returned in one response).

    Current enrollment (level/section) is resolved via one bulk query over
    the current PAGE's students, not one query per student - the previous
    version called `s.enrollments.filter(...)` inside the loop, an N+1
    that paginating down to 20 rows/page mostly masks but doesn't excuse.
    """

    permission_classes = [IsAuthenticated, HasPermission("view_student")]
    pagination_class = StandardResultsPagination

    def get(self, request):
        unenrolled_only = request.query_params.get("unenrolled") == "true"

        students = Student.objects.select_related("profile").order_by(
            "profile__first_name", "profile__last_name", "enrollment_id"
        )
        if unenrolled_only:
            students = students.filter(profile__user_id__isnull=True)

        # Optional bounded server-side narrowing (used by pickers): every
        # whitespace-separated term must match a name or the enrollment id.
        for term in (request.query_params.get("search") or "").split()[:5]:
            students = students.filter(
                Q(profile__first_name__icontains=term)
                | Q(profile__middle_name__icontains=term)
                | Q(profile__last_name__icontains=term)
                | Q(enrollment_id__icontains=term)
            )
        status_param = request.query_params.get("status")
        if status_param:
            allowed = {choice for choice, _ in Student._meta.get_field("status").choices}
            wanted = [value for value in status_param.split(",") if value in allowed]
            students = students.filter(status__in=wanted) if wanted else students.none()

        paginator = self.pagination_class()
        page = paginator.paginate_queryset(students, request, view=self)
        page_students = page if page is not None else students

        current_by_student_id = {
            sl.student_id: sl
            for sl in StudentLevel.objects.filter(
                student_id__in=[s.id for s in page_students], is_current=True
            ).select_related("level", "section")
        }

        data = []
        for s in page_students:
            current = current_by_student_id.get(s.id)
            data.append(
                {
                    "id": s.id,
                    "first_name": s.profile.first_name,
                    "middle_name": s.profile.middle_name,
                    "last_name": s.profile.last_name,
                    "full_name": f"{s.profile.first_name} {s.profile.middle_name + ' ' if s.profile.middle_name else ''}{s.profile.last_name}",
                    "enrollment_id": s.enrollment_id,
                    "level": current.level.name if current and current.level else "N/A",
                    "section": (
                        current.section.name if current and current.section else "N/A"
                    ),
                    "status": s.status,
                    "has_account": s.profile.user_id is not None,
                    "apaar_id": s.apaar_id,
                    "pen": s.pen,
                    "caste_category": s.caste_category,
                    "is_rte": s.is_rte,
                }
            )

        if page is not None:
            return paginator.get_paginated_response(data)
        return Response(data)


class PortalActivationView(APIView):
    """
    Creates user accounts for existing student profiles.
    Expects a list of enrollment objects.
    """

    permission_classes = [IsAuthenticated, HasPermission("add_student")]

    @transaction.atomic
    def post(self, request):
        enrollment_list = request.data.get("enrollments", [])
        if not isinstance(enrollment_list, list):
            return Response(
                {"error": "Expected a list of enrollments under the 'enrollments' key"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        results = []
        errors = []

        from .serializers import BulkAccountCreationSerializer

        for index, enrollment_data in enumerate(enrollment_list):
            serializer = BulkAccountCreationSerializer(data=enrollment_data)
            if serializer.is_valid():
                try:
                    user = serializer.save()
                    results.append(
                        {
                            "index": index,
                            "username": user.username,
                            "student_id": enrollment_data["student_id"],
                        }
                    )
                except Exception as e:
                    errors.append({"index": index, "error": str(e)})
            else:
                errors.append({"index": index, "errors": serializer.errors})

        if errors:
            transaction.set_rollback(True)
            return Response(
                {"message": "Portal activation failed", "errors": errors},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            {
                "message": f"Successfully activated portal for {len(results)} students",
                "results": results,
            },
            status=status.HTTP_201_CREATED,
        )


class CredentialDistributionView(APIView):
    """
    Lists students who have been activated but haven't changed their password.
    Includes their initial temporary password.
    Optimized to prevent N+1 queries.
    """

    permission_classes = [IsAuthenticated, HasPermission("view_student")]

    def get(self, request):
        from django.apps import apps

        User = apps.get_model("accounts", "User")

        # 1. Fetch Students
        students = Student.objects.filter(
            profile__user_id__isnull=False
        ).select_related("profile")

        # 2. Collect User IDs
        user_ids = [s.profile.user_id for s in students if s.profile.user_id]

        if not user_ids:
            return Response([])

        # 3. Bulk Fetch Users (1 Query)
        users = User.objects.filter(id__in=user_ids)
        user_map = {u.id: u for u in users}

        data = []
        for s in students:
            user = user_map.get(s.profile.user_id)

            if user and user.needs_password_change and user.initial_password_display:
                data.append(
                    {
                        "id": s.id,
                        "full_name": f"{s.profile.first_name} {s.profile.last_name}",
                        "enrollment_id": s.enrollment_id,
                        "username": s.profile.local_username or user.username,
                        "initial_password": decrypt_secret(user.initial_password_display),
                    }
                )

        if data:
            log_action(
                request,
                action="credentials_viewed",
                model_name="Student",
                object_id=",".join(str(d["id"]) for d in data),
            )

        return Response(data)


class StudentDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get_permissions(self):
        if self.request.method in ["PUT", "PATCH"]:
            return [IsAuthenticated(), HasPermission("change_student")]
        elif self.request.method == "DELETE":
            return [IsAuthenticated(), HasPermission("delete_student")]
        return [IsAuthenticated(), HasPermission("view_student")]

    def get(self, request, pk):
        try:
            student = Student.objects.select_related("profile").get(id=pk)
        except Student.DoesNotExist:
            return Response(
                {"error": "Student not found"}, status=status.HTTP_404_NOT_FOUND
            )

        current = student.enrollments.filter(is_current=True).first()

        # We need parents for the edit form
        parents_data = []
        relations = student.parent_links.select_related("parent__profile").all()
        for rel in relations:
            p_profile = rel.parent.profile
            parents_data.append(
                {
                    "first_name": p_profile.first_name,
                    "last_name": p_profile.last_name,
                    "phone": p_profile.phone,
                    "gender": p_profile.gender,
                    "occupation": rel.parent.occupation,
                    "relation": rel.relation_type,
                    "is_primary": rel.is_primary_contact,
                }
            )

        data = {
            "id": student.id,
            "first_name": student.profile.first_name,
            "middle_name": student.profile.middle_name,
            "last_name": student.profile.last_name,
            "enrollment_id": student.enrollment_id,
            "gender": student.profile.gender,
            "date_of_birth": student.profile.date_of_birth,
            "email": student.profile.user.email if student.profile.user_id else None,
            "phone": student.profile.phone,
            "address": student.profile.address,
            # Academic
            "level_id": current.level.id if current and current.level else None,
            "section_id": current.section.id if current and current.section else None,
            "level": (
                current.level.name if current and current.level else ""
            ),  # Keep legacy for display if needed
            "section": current.section.name if current and current.section else "",
            "academic_year": current.academic_year if current else "",
            "admission_date": student.admission_date,
            "apaar_id": student.apaar_id,
            "pen": student.pen,
            "caste_category": student.caste_category,
            "is_rte": student.is_rte,
            "aadhaar_last_4": student.aadhaar_last_4,
            "mother_tongue": student.mother_tongue,
            "social_category": student.social_category,
            "religion": student.religion,
            "mother_name": student.get_mother_name(),
            "father_name": student.get_father_name(),
            "guardian_name": student.get_guardian_name(),
            "parents": parents_data,  # Include parents for editing
        }

        # Add previous academic history if exists
        history = student.academic_history.first()
        if history:
            data["previous_school"] = history.previous_school
            data["last_grade_passed"] = history.last_grade_passed

        return Response(data)

    def put(self, request, pk):
        try:
            student = Student.objects.select_related("profile").get(id=pk)
        except Student.DoesNotExist:
            return Response(
                {"error": "Student not found"}, status=status.HTTP_404_NOT_FOUND
            )

        serializer = StudentEnrollmentSerializer(
            student, data=request.data, partial=True
        )
        if serializer.is_valid():
            serializer.save()
            return Response({"message": "Student updated successfully"})
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @transaction.atomic
    def delete(self, request, pk):
        try:
            student = Student.objects.select_related("profile").get(id=pk)
        except Student.DoesNotExist:
            return Response(
                {"error": "Student not found"}, status=status.HTTP_404_NOT_FOUND
            )

        user_id = student.profile.user_id

        # Profile deletion handling
        # Since 'profile' is OneToOne on Student model with CASCADE, deleting student *might* not delete profile
        # if the FK is on Student. We must check Student model definition.
        # Student model: profile = OneToOneField("profiles.Profile", ...)
        # So Student -> Profile.
        # Deleting Student does NOT cascade to Profile.
        # We must delete Profile explicitly.
        profile = student.profile

        student.delete()
        profile.delete()

        if user_id:
            from django.apps import apps
            from django.db import connection

            User = apps.get_model("accounts", "User")
            UserRole = apps.get_model("roles", "UserRole")

            # Remove student role in THIS tenant's schema
            UserRole.objects.filter(
                user__id=user_id,
                role__slug="student",
            ).delete()

            # Check for orphans - if user has NO roles in THIS tenant
            # Note: UserRole is now tenant-scoped, so this check is schema-specific
            if not UserRole.objects.filter(user__id=user_id).exists():
                try:
                    User.objects.get(id=user_id).delete()
                except User.DoesNotExist:
                    pass

        return Response(status=status.HTTP_204_NO_CONTENT)


# === PROMOTION & TRANSFER ===

def _resolve_promotion_entries(entries_data):
    """
    Resolves student/target_level/target_section UUIDs (from the request
    body) to model instances. Any entry whose student_id doesn't resolve
    to a real Student is reported immediately as a clean per-student skip
    - never passed into the service layer, and never surfaced as a 500.
    """
    from academics.models import Section

    student_ids = {e["student"] for e in entries_data}
    students = {s.id: s for s in Student.objects.filter(id__in=student_ids)}

    level_ids = {e["target_level"] for e in entries_data if e.get("target_level")}
    levels = {lvl.id: lvl for lvl in AcademicLevel.objects.filter(id__in=level_ids)}

    section_ids = {e["target_section"] for e in entries_data if e.get("target_section")}
    sections = {s.id: s for s in Section.objects.filter(id__in=section_ids)}

    resolved = []
    immediate_errors = []

    for e in entries_data:
        student = students.get(e["student"])
        if student is None:
            immediate_errors.append(
                {"student": str(e["student"]), "action": e["action"], "error": "Student not found."}
            )
            continue

        target_level_obj = None
        if e.get("target_level"):
            target_level_obj = levels.get(e["target_level"])
            if target_level_obj is None:
                immediate_errors.append(
                    {"student": str(e["student"]), "action": e["action"], "error": "Target level not found."}
                )
                continue

        target_section_obj = None
        if e.get("target_section"):
            target_section_obj = sections.get(e["target_section"])
            if target_section_obj is None:
                immediate_errors.append(
                    {"student": str(e["student"]), "action": e["action"], "error": "Target section not found."}
                )
                continue

        resolved.append(
            {
                "student": student,
                "action": e["action"],
                "target_academic_year": e.get("target_academic_year", ""),
                "target_level_obj": target_level_obj,
                "target_section_obj": target_section_obj,
                "reason": e.get("reason", ""),
            }
        )

    return resolved, immediate_errors


class PromotionCandidatesView(APIView):
    """GET only - no writes. Only active students appear (get_promotion_candidates
    filters student__status="active")."""

    permission_classes = [IsAuthenticated, HasPermission("manage_student_promotion")]

    def get(self, request):
        academic_year = request.query_params.get("academic_year")
        level_id = request.query_params.get("level")
        section_id = request.query_params.get("section")

        if not academic_year or not level_id:
            return Response(
                {"error": "'academic_year' and 'level' query parameters are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        candidates = list(get_promotion_candidates(academic_year, level_id, section_id))

        # Phase 9E: fee/exam warnings computed in bulk for every candidate at
        # once (same formulas as get_fee_warning()/get_exam_warning(), just
        # evaluated once for the whole page of candidates instead of once
        # per candidate) - this view uses one shared `academic_year` for
        # every candidate, so the same value is looked up for each student_id.
        candidate_students = [sl.student for sl in candidates]
        fee_warnings = get_fee_warnings_bulk(candidate_students)
        exam_warnings = get_exam_warnings_bulk(
            candidate_students, {s.id: academic_year for s in candidate_students}
        )

        data = []
        for sl in candidates:
            student = sl.student
            next_level = get_next_level(sl.level) if sl.level_id else None
            data.append(
                {
                    "student_id": str(student.id),
                    "full_name": f"{student.profile.first_name} {student.profile.last_name}",
                    "enrollment_id": student.enrollment_id,
                    "current_level": str(sl.level_id) if sl.level_id else None,
                    "current_level_name": sl.level.name if sl.level_id else None,
                    "current_section": str(sl.section_id) if sl.section_id else None,
                    "current_section_name": sl.section.name if sl.section_id else None,
                    "default_target_level": str(next_level.id) if next_level else None,
                    "default_target_level_name": next_level.name if next_level else None,
                    "fee_warning": fee_warnings.get(student.id),
                    "exam_warning": exam_warnings.get(student.id),
                }
            )

        return Response(data)


class PromotionPreviewView(APIView):
    """POST - pure computation, no writes."""

    permission_classes = [IsAuthenticated, HasPermission("manage_student_promotion")]

    def post(self, request):
        serializer = PromotionBatchInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        resolved, immediate_errors = _resolve_promotion_entries(serializer.validated_data["entries"])
        results = preview_lifecycle_actions(entries=resolved) if resolved else []

        results += [
            {
                "student": e["student"],
                "action": e["action"],
                "eligible": False,
                "conflicts": [e["error"]],
                "warnings": [],
                "source_academic_year": None,
                "target_academic_year": None,
                "target_level": None,
                "target_section": None,
            }
            for e in immediate_errors
        ]

        return Response(results)


class PromotionExecuteView(APIView):
    """POST - the atomic bulk operation. One invalid student is skipped
    and reported, never aborting the whole batch."""

    permission_classes = [IsAuthenticated, HasPermission("manage_student_promotion")]

    ACTION_EVENT_MAP = {
        "promoted": "student_promoted",
        "retained": "student_retained",
        "transferred": "student_transferred",
        "withdrawn": "student_withdrawn",
        "graduated": "student_graduated",
    }

    def post(self, request):
        serializer = PromotionBatchInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        resolved, immediate_errors = _resolve_promotion_entries(serializer.validated_data["entries"])
        staff_member = get_staff_member_for_user(request.user)

        results = execute_lifecycle_actions(entries=resolved, created_by=staff_member) if resolved else []
        results += [
            {"student": e["student"], "action": e["action"], "status": "skipped", "error": e["error"]}
            for e in immediate_errors
        ]

        successes = [r for r in results if r["status"] == "success"]
        if successes:
            by_action = {}
            for r in successes:
                by_action.setdefault(r["action"], []).append(r["student"])

            for action, student_ids in by_action.items():
                log_action(
                    request,
                    action=self.ACTION_EVENT_MAP.get(action, action),
                    model_name="PromotionRecord",
                    object_id=None,
                    changes={
                        "source_academic_year": serializer.validated_data["source_academic_year"],
                        "student_count": len(student_ids),
                        "student_ids": student_ids,
                    },
                )

        return Response({"results": results})


class PromotionHistoryView(APIView):
    """Paginated (StandardResultsPagination) - this grows by design (one
    row per student per lifecycle event, append-only, never deleted), so
    an unpaginated response here would grow unbounded over the school's
    lifetime even though today's demo dataset is a modest 437 rows."""

    permission_classes = [IsAuthenticated, HasPermission("manage_student_promotion")]
    pagination_class = StandardResultsPagination

    def get(self, request):
        qs = PromotionRecord.objects.select_related(
            "student__profile", "source_level", "target_level", "source_section", "target_section"
        ).order_by("-created_at")
        student_id = request.query_params.get("student")
        academic_year = request.query_params.get("academic_year")
        action = request.query_params.get("action")
        if student_id:
            qs = qs.filter(student_id=student_id)
        if academic_year:
            qs = qs.filter(
                Q(source_academic_year=academic_year) | Q(target_academic_year=academic_year)
            )
        if action:
            qs = qs.filter(action=action)

        paginator = self.pagination_class()
        page = paginator.paginate_queryset(qs, request, view=self)
        if page is not None:
            return paginator.get_paginated_response(PromotionRecordSerializer(page, many=True).data)
        return Response(PromotionRecordSerializer(qs, many=True).data)


class PromotionReverseView(APIView):
    permission_classes = [IsAuthenticated, HasPermission("manage_student_promotion")]

    def post(self, request, record_id):
        record = get_object_or_404(PromotionRecord, id=record_id)
        staff_member = get_staff_member_for_user(request.user)

        reversal = reverse_promotion(record=record, created_by=staff_member)

        log_action(
            request,
            action="promotion_reversed",
            model_name="PromotionRecord",
            object_id=reversal.id,
            changes={"original_promotion_record_id": str(record.id), "student": str(record.student_id)},
        )
        return Response(PromotionRecordSerializer(reversal).data, status=status.HTTP_201_CREATED)


class UdiseExportView(APIView):
    permission_classes = [IsAuthenticated, HasPermission("view_student")]

    def get(self, request):
        from .exports import export_udise_plus_csv
        students = Student.objects.filter(status="active").select_related("profile").prefetch_related("enrollments__level", "enrollments__section", "parent_links__parent__profile")
        return export_udise_plus_csv(students)


class CbseLocExportView(APIView):
    permission_classes = [IsAuthenticated, HasPermission("view_student")]

    def get(self, request):
        from .exports import export_cbse_loc_csv
        level_id = request.query_params.get("level")
        students = Student.objects.filter(status="active").select_related("profile").prefetch_related("enrollments__level__subjects", "enrollments__section", "parent_links__parent__profile")
        if level_id:
            students = students.filter(enrollments__level_id=level_id, enrollments__is_current=True)
        return export_cbse_loc_csv(students)
