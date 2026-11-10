from django.db.models import Prefetch, Q
from core.query_params import model_param
from rest_framework import viewsets, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.utils.crypto import decrypt_secret
from core.audit import log_action
from core.pagination import StandardResultsPagination
from roles.permissions import HasPermission

from .models import Parent, StudentParentRelation
from .serializers import (
    ParentPortalActivationSerializer,
    ParentSerializer,
    StudentParentRelationSerializer,
)


class ParentViewSet(viewsets.ModelViewSet):
    queryset = Parent.objects.all().select_related(
        "profile", "profile__student_record", "profile__staff_record"
    ).prefetch_related(
        Prefetch("student_links", queryset=StudentParentRelation.objects.select_related("student__profile"))
    ).order_by(
        "profile__first_name", "profile__last_name"
    )
    serializer_class = ParentSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = StandardResultsPagination

    def get_permissions(self):
        if self.action in ["list", "retrieve"]:
            return [permissions.IsAuthenticated(), HasPermission("view_family")]
        if self.action == "create":
            return [permissions.IsAuthenticated(), HasPermission("add_family")]
        if self.action in ["update", "partial_update"]:
            return [permissions.IsAuthenticated(), HasPermission("change_family")]
        if self.action == "destroy":
            return [permissions.IsAuthenticated(), HasPermission("delete_family")]
        return [permissions.IsAuthenticated(), HasPermission("view_family")]

    def get_queryset(self):
        qs = super().get_queryset()

        student_id = model_param(self.request, "student", StudentParentRelation, "student")
        if student_id is not None:
            qs = qs.filter(student_links__student_id=student_id)

        search = (self.request.query_params.get("search") or "").strip()
        if search:
            terms = search.split()[:5]
            for term in terms:
                qs = qs.filter(
                    Q(profile__first_name__icontains=term)
                    | Q(profile__middle_name__icontains=term)
                    | Q(profile__last_name__icontains=term)
                    | Q(profile__phone__icontains=term)
                )
        return qs.distinct()


class StudentParentRelationViewSet(viewsets.ModelViewSet):
    queryset = StudentParentRelation.objects.all().select_related(
        "student__profile", "parent__profile"
    ).order_by("-id")
    serializer_class = StudentParentRelationSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = StandardResultsPagination

    def get_permissions(self):
        if self.action in ["list", "retrieve"]:
            return [permissions.IsAuthenticated(), HasPermission("view_family")]
        if self.action == "create":
            return [permissions.IsAuthenticated(), HasPermission("add_family")]
        if self.action in ["update", "partial_update"]:
            return [permissions.IsAuthenticated(), HasPermission("change_family")]
        if self.action == "destroy":
            return [permissions.IsAuthenticated(), HasPermission("delete_family")]
        return [permissions.IsAuthenticated(), HasPermission("view_family")]

    def get_queryset(self):
        qs = super().get_queryset()
        student_id = model_param(self.request, "student", qs.model, "student")
        if student_id is not None:
            qs = qs.filter(student_id=student_id)
        parent_id = model_param(self.request, "parent", qs.model, "parent")
        if parent_id is not None:
            qs = qs.filter(parent_id=parent_id)
        return qs


class ParentPortalActivationView(APIView):
    """
    Creates a User account for an existing Parent record. Mirrors
    students.PortalActivationView / staff.StaffActivationView - see
    ParentPortalActivationSerializer for the account-creation logic.

    Gated by 'change_family' (an existing, already-seeded permission) rather
    than a new codename - the Parent Portal spec explicitly limits new
    permissions to the 4 parent-facing ones (view_own_children,
    view_child_attendance, view_child_timetable, view_child_results), none
    of which are appropriate for an admin-side activation action.
    """

    permission_classes = [permissions.IsAuthenticated, HasPermission("change_family")]

    def post(self, request):
        serializer = ParentPortalActivationSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            return Response(
                {
                    "message": "Parent account activated successfully",
                    "username": user.username,
                },
                status=status.HTTP_201_CREATED,
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ParentCredentialDistributionView(APIView):
    """
    Lists parents who have been activated but haven't changed their password.
    Mirrors students.CredentialDistributionView / staff.CredentialDistributionView
    exactly, including the audit-on-view behavior.
    """

    permission_classes = [permissions.IsAuthenticated, HasPermission("view_family")]

    def get(self, request):
        from django.apps import apps

        User = apps.get_model("accounts", "User")

        parents = Parent.objects.filter(
            profile__user_id__isnull=False
        ).select_related("profile")

        user_ids = [p.profile.user_id for p in parents if p.profile.user_id]
        if not user_ids:
            return Response([])

        users = User.objects.filter(id__in=user_ids)
        user_map = {u.id: u for u in users}

        data = []
        for p in parents:
            user = user_map.get(p.profile.user_id)
            if user and user.needs_password_change and user.initial_password_display:
                data.append(
                    {
                        "id": str(p.id),
                        "full_name": f"{p.profile.first_name} {p.profile.last_name}",
                        "username": p.profile.local_username or user.username,
                        "initial_password": decrypt_secret(user.initial_password_display),
                    }
                )

        if data:
            log_action(
                request,
                action="credentials_viewed",
                model_name="Parent",
                object_id=",".join(d["id"] for d in data),
            )

        return Response(data)
