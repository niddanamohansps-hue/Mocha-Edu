"""
EduSekai Staff Leave Management API Views (Phase 5)

Full REST API for leave types, balances, applications, approvals,
attendance sync, and timetable substitute teacher matching.
"""

import os
from django.conf import settings
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import FileResponse, Http404, HttpResponse
from django.shortcuts import get_object_or_404
from core.query_params import model_param
from rest_framework import status, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.tenant_access import HasAnyPermission, IsTenantMember
from core.pagination import StandardResultsPagination
from roles.permissions import HasPermission

from .leave_serializers import (
    AssignSubstitutionSerializer,
    LeaveApplicationApproveSerializer,
    LeaveApplicationCancelSerializer,
    LeaveApplicationCreateSerializer,
    LeaveApplicationDetailSerializer,
    LeaveApplicationListSerializer,
    LeaveApplicationRejectSerializer,
    LeaveTypeSerializer,
    StaffLeaveBalanceAdjustSerializer,
    StaffLeaveBalanceSerializer,
)
from .leave_services import (
    approve_leave_application,
    assign_leave_substitution,
    cancel_leave_application,
    get_affected_periods_and_substitutes,
    get_current_academic_year,
    get_or_create_staff_balances,
    get_staff_member_for_user,
    reject_leave_application,
    submit_leave_application,
)
from .models import (
    LeaveApplication,
    LeaveType,
    StaffLeaveBalance,
    StaffMember,
)


class LeaveTypeViewSet(viewsets.ModelViewSet):
    """
    CRUD for tenant leave categories.
    - Reading requires tenant membership and one of: 'apply_staff_leave', 'manage_leave_types',
      'manage_staff_leaves', 'view_all_leaves'. Only 'manage_leave_types' holders see inactive types.
    - Creating, modifying, or deactivating requires 'manage_leave_types'.
    - No PUT: partial updates (PATCH) are the supported way to edit a leave type.
    """
    queryset = LeaveType.objects.all()
    serializer_class = LeaveTypeSerializer
    pagination_class = None
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def get_permissions(self):
        if self.action in ["list", "retrieve"]:
            return [
                IsAuthenticated(),
                IsTenantMember(),
                HasAnyPermission(
                    "apply_staff_leave",
                    "manage_leave_types",
                    "manage_staff_leaves",
                    "view_all_leaves",
                ),
            ]
        return [IsAuthenticated(), IsTenantMember(), HasPermission("manage_leave_types")]

    def get_queryset(self):
        qs = super().get_queryset()
        # Non-admins only see active types
        user = self.request.user
        has_manage = HasPermission("manage_leave_types").has_permission(self.request, self)
        if not has_manage:
            qs = qs.filter(is_active=True)
        return qs

    def perform_destroy(self, instance):
        # Soft delete if applications reference it
        if instance.applications.exists() or instance.staff_balances.exists():
            instance.is_active = False
            instance.save(update_fields=["is_active"])
        else:
            instance.delete()


class StaffLeaveBalanceMyView(APIView):
    """
    GET /api/staff/leaves/balances/my/
    Returns the caller's leave balances for the active academic year.
    Auto-initializes quotas for active leave types if not yet created.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        staff = get_staff_member_for_user(request.user)
        if not staff:
            return Response(
                {"error": "Authenticated user is not linked to an active staff member profile."},
                status=status.HTTP_403_FORBIDDEN,
            )

        ref, year_name = get_current_academic_year()
        academic_year = request.query_params.get("academic_year", year_name)

        balances = get_or_create_staff_balances(staff, academic_year, academic_year_ref=ref)
        serializer = StaffLeaveBalanceSerializer(balances, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class StaffLeaveBalanceListView(APIView):
    """
    GET /api/staff/leaves/balances/
    Lists balances across all staff. Requires 'view_all_leaves' or 'manage_staff_leaves'.
    """
    permission_classes = [IsAuthenticated]
    pagination_class = StandardResultsPagination

    def get(self, request):
        can_view = (
            HasPermission("view_all_leaves").has_permission(request, self)
            or HasPermission("manage_staff_leaves").has_permission(request, self)
        )
        if not can_view:
            return Response(
                {"error": "You do not have permission to view all staff leave balances."},
                status=status.HTTP_403_FORBIDDEN,
            )

        qs = StaffLeaveBalance.objects.select_related("staff__profile", "leave_type").order_by("staff__profile__first_name")

        staff_id = model_param(request, "staff", qs.model, "staff")
        if staff_id is not None:
            qs = qs.filter(staff_id=staff_id)

        academic_year = request.query_params.get("academic_year")
        if academic_year:
            qs = qs.filter(academic_year=academic_year)

        leave_type_id = model_param(request, "leave_type", qs.model, "leave_type")
        if leave_type_id is not None:
            qs = qs.filter(leave_type_id=leave_type_id)

        paginator = self.pagination_class()
        page = paginator.paginate_queryset(qs, request, view=self)
        if page is not None:
            return paginator.get_paginated_response(StaffLeaveBalanceSerializer(page, many=True).data)

        return Response(StaffLeaveBalanceSerializer(qs, many=True).data)


class StaffLeaveBalanceAdjustView(APIView):
    """
    POST /api/staff/leaves/balances/adjust/
    Adjusts allocated days for a staff member. Requires 'manage_leave_types'.
    """
    permission_classes = [IsAuthenticated, HasPermission("manage_leave_types")]

    def post(self, request):
        serializer = StaffLeaveBalanceAdjustSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        staff = get_object_or_404(StaffMember, id=data["staff_id"])
        leave_type = get_object_or_404(LeaveType, id=data["leave_type_id"])

        balance, _ = StaffLeaveBalance.objects.get_or_create(
            staff=staff,
            leave_type=leave_type,
            academic_year=data["academic_year"],
            defaults={"allocated_days": data["allocated_days"]},
        )
        balance.allocated_days = data["allocated_days"]
        balance.save(update_fields=["allocated_days", "updated_at"])

        return Response(StaffLeaveBalanceSerializer(balance).data, status=status.HTTP_200_OK)


class LeaveApplicationMyListView(APIView):
    """
    GET /api/staff/leaves/applications/my/
    Lists the caller's leave applications.
    """
    permission_classes = [IsAuthenticated]
    pagination_class = StandardResultsPagination

    def get(self, request):
        staff = get_staff_member_for_user(request.user)
        if not staff:
            return Response(
                {"error": "Authenticated user is not linked to an active staff member profile."},
                status=status.HTTP_403_FORBIDDEN,
            )

        qs = (
            LeaveApplication.objects.filter(staff=staff)
            .select_related("leave_type", "staff__profile")
            .order_by("-applied_at")
        )

        status_param = request.query_params.get("status")
        if status_param:
            qs = qs.filter(status=status_param)

        academic_year = request.query_params.get("academic_year")
        if academic_year:
            qs = qs.filter(academic_year=academic_year)

        paginator = self.pagination_class()
        page = paginator.paginate_queryset(qs, request, view=self)
        if page is not None:
            return paginator.get_paginated_response(LeaveApplicationListSerializer(page, many=True).data)

        return Response(LeaveApplicationListSerializer(qs, many=True).data)


class LeaveApplicationCreateView(APIView):
    """
    POST /api/staff/leaves/applications/
    Applies for leave on behalf of the authenticated staff member.
    """
    permission_classes = [IsAuthenticated, HasPermission("apply_staff_leave")]

    def post(self, request):
        staff = get_staff_member_for_user(request.user)
        if not staff:
            return Response(
                {"error": "Authenticated user is not linked to an active staff member profile."},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = LeaveApplicationCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        leave_type = get_object_or_404(LeaveType, id=data["leave_type_id"])

        try:
            application = submit_leave_application(
                staff=staff,
                leave_type=leave_type,
                start_date=data["start_date"],
                end_date=data["end_date"],
                reason=data["reason"],
                is_half_day=data.get("is_half_day", False),
                half_day_session=data.get("half_day_session", ""),
                document=data.get("document"),
                academic_year=data.get("academic_year"),
                request=request,
            )
        except ValidationError as err:
            return Response(
                err.message_dict if hasattr(err, "message_dict") else {"error": err.messages[0]},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            LeaveApplicationDetailSerializer(application).data,
            status=status.HTTP_201_CREATED,
        )


class LeaveApplicationDetailView(APIView):
    """
    GET /api/staff/leaves/applications/<uuid:pk>/
    Object-level authorized detail view.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        application = get_object_or_404(
            LeaveApplication.objects.select_related(
                "staff__profile", "leave_type"
            ).prefetch_related("approvals__approver__profile"),
            pk=pk,
        )

        # Authorization: caller must be applicant OR possess view_all_leaves/manage_staff_leaves
        is_applicant = (
            application.staff.profile.user_id
            and str(application.staff.profile.user_id) == str(request.user.id)
        )
        can_view_all = (
            HasPermission("view_all_leaves").has_permission(request, self)
            or HasPermission("manage_staff_leaves").has_permission(request, self)
        )

        if not is_applicant and not can_view_all:
            return Response(
                {"error": "You do not have permission to view this leave application."},
                status=status.HTTP_403_FORBIDDEN,
            )

        return Response(
            LeaveApplicationDetailSerializer(application).data,
            status=status.HTTP_200_OK,
        )


class LeaveApplicationCancelView(APIView):
    """
    POST /api/staff/leaves/applications/<uuid:pk>/cancel/
    Cancels a leave application and reconciles balance and attendance.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        application = get_object_or_404(LeaveApplication, pk=pk)
        staff = get_staff_member_for_user(request.user)
        is_admin = HasPermission("manage_staff_leaves").has_permission(request, self)

        serializer = LeaveApplicationCancelSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        reason = serializer.validated_data.get("reason", "")

        try:
            cancelled = cancel_leave_application(
                application_id=application.id,
                actor_staff=staff,
                reason=reason,
                is_admin=is_admin,
                request=request,
            )
        except PermissionDenied as err:
            return Response({"error": str(err)}, status=status.HTTP_403_FORBIDDEN)
        except ValidationError as err:
            return Response({"error": str(err)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            LeaveApplicationDetailSerializer(cancelled).data,
            status=status.HTTP_200_OK,
        )


class ApproverInboxView(APIView):
    """
    GET /api/staff/leaves/approvals/inbox/
    Inbox of leave applications requiring administrative review.
    """
    permission_classes = [IsAuthenticated, HasPermission("manage_staff_leaves")]
    pagination_class = StandardResultsPagination

    def get(self, request):
        status_filter = request.query_params.get("status", "pending")
        qs = (
            LeaveApplication.objects.select_related("staff__profile", "leave_type")
            .order_by("-applied_at")
        )
        if status_filter:
            qs = qs.filter(status=status_filter)

        staff_id = model_param(request, "staff", qs.model, "staff")
        if staff_id is not None:
            qs = qs.filter(staff_id=staff_id)

        paginator = self.pagination_class()
        page = paginator.paginate_queryset(qs, request, view=self)
        if page is not None:
            return paginator.get_paginated_response(LeaveApplicationListSerializer(page, many=True).data)

        return Response(LeaveApplicationListSerializer(qs, many=True).data)


class LeaveApplicationApproveView(APIView):
    """
    POST /api/staff/leaves/applications/<uuid:pk>/approve/
    Approves an application. Enforces no self-approval.
    """
    permission_classes = [IsAuthenticated, HasPermission("manage_staff_leaves")]

    def post(self, request, pk):
        approver = get_staff_member_for_user(request.user)
        serializer = LeaveApplicationApproveSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        comments = serializer.validated_data.get("comments", "")

        try:
            approved = approve_leave_application(
                application_id=pk,
                approver_staff=approver,
                comments=comments,
                request=request,
            )
        except PermissionDenied as err:
            return Response({"error": str(err)}, status=status.HTTP_403_FORBIDDEN)
        except ValidationError as err:
            return Response({"error": str(err)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            LeaveApplicationDetailSerializer(approved).data,
            status=status.HTTP_200_OK,
        )


class LeaveApplicationRejectView(APIView):
    """
    POST /api/staff/leaves/applications/<uuid:pk>/reject/
    Rejects an application. Mandatory rejection reason.
    """
    permission_classes = [IsAuthenticated, HasPermission("manage_staff_leaves")]

    def post(self, request, pk):
        approver = get_staff_member_for_user(request.user)
        serializer = LeaveApplicationRejectSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        comments = serializer.validated_data["comments"]

        try:
            rejected = reject_leave_application(
                application_id=pk,
                approver_staff=approver,
                comments=comments,
                request=request,
            )
        except PermissionDenied as err:
            return Response({"error": str(err)}, status=status.HTTP_403_FORBIDDEN)
        except ValidationError as err:
            return Response({"error": str(err)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            LeaveApplicationDetailSerializer(rejected).data,
            status=status.HTTP_200_OK,
        )


class LeaveApplicationDocumentDownloadView(APIView):
    """
    GET /api/staff/leaves/applications/<uuid:pk>/document/
    Secured document download. Protected against path traversal and unauthenticated access.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        application = get_object_or_404(LeaveApplication, pk=pk)
        if not application.document:
            raise Http404("Leave application has no attached document.")

        # Authorization: caller is applicant OR has manage/view permissions
        is_applicant = (
            application.staff.profile.user_id
            and str(application.staff.profile.user_id) == str(request.user.id)
        )
        can_view_all = (
            HasPermission("view_all_leaves").has_permission(request, self)
            or HasPermission("manage_staff_leaves").has_permission(request, self)
        )

        if not is_applicant and not can_view_all:
            return Response(
                {"error": "You do not have permission to access this document."},
                status=status.HTTP_403_FORBIDDEN,
            )

        # X-Accel-Redirect delivery mode if enabled
        if getattr(settings, "USE_X_ACCEL_REDIRECT", False):
            response = HttpResponse()
            prefix = getattr(settings, "X_ACCEL_PREFIX", "/protected_media/").rstrip("/")
            response["X-Accel-Redirect"] = f"{prefix}/{application.document.name}"
            response["Content-Disposition"] = f'attachment; filename="{os.path.basename(application.document.name)}"'
            return response

        try:
            return FileResponse(
                application.document.open("rb"),
                as_attachment=True,
                filename=os.path.basename(application.document.name),
            )
        except Exception:
            raise Http404("Document could not be read from storage.")


class LeaveApplicationAffectedPeriodsView(APIView):
    """
    GET /api/staff/leaves/applications/<uuid:pk>/affected-periods/
    Returns teaching periods impacted by an instructor's leave,
    along with eligible, free substitute instructors.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        application = get_object_or_404(LeaveApplication.objects.select_related("staff"), pk=pk)

        is_applicant = (
            application.staff.profile.user_id
            and str(application.staff.profile.user_id) == str(request.user.id)
        )
        can_manage = (
            HasPermission("view_all_leaves").has_permission(request, self)
            or HasPermission("manage_staff_leaves").has_permission(request, self)
        )

        if not is_applicant and not can_manage:
            return Response(
                {"error": "You do not have permission to inspect timetable impact for this application."},
                status=status.HTTP_403_FORBIDDEN,
            )

        slots = get_affected_periods_and_substitutes(application)
        return Response(slots, status=status.HTTP_200_OK)


class AssignLeaveSubstitutionView(APIView):
    """
    POST /api/staff/leaves/substitutions/assign/
    Assigns an eligible substitute instructor for a specific timetable period.
    """
    permission_classes = [IsAuthenticated, HasPermission("manage_staff_leaves")]

    def post(self, request):
        staff = get_staff_member_for_user(request.user)
        serializer = AssignSubstitutionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        try:
            sub = assign_leave_substitution(
                entry_id=data["entry_id"],
                date_val=data["date"],
                substitute_instructor_id=data["substitute_instructor_id"],
                reason=data["reason"],
                created_by=staff,
                request=request,
            )
        except ValidationError as err:
            return Response({"error": str(err)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            {
                "id": str(sub.id),
                "timetable_entry": str(sub.timetable_entry_id),
                "date": str(sub.date),
                "substitute_instructor": (
                    f"{sub.substitute_instructor.staff_member.profile.first_name} "
                    f"{sub.substitute_instructor.staff_member.profile.last_name}"
                )
                if sub.substitute_instructor
                else None,
                "reason": sub.reason,
            },
            status=status.HTTP_201_CREATED,
        )
