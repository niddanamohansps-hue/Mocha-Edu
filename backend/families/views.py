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
    queryset = Parent.objects.all().select_related("profile").order_by(
        "profile__first_name", "profile__last_name"
    )
    serializer_class = ParentSerializer
    permission_classes = [permissions.IsAuthenticated, HasPermission("manage_students")]
    pagination_class = StandardResultsPagination


class StudentParentRelationViewSet(viewsets.ModelViewSet):
    queryset = StudentParentRelation.objects.all().order_by("-id")
    serializer_class = StudentParentRelationSerializer
    permission_classes = [permissions.IsAuthenticated, HasPermission("manage_students")]
    pagination_class = StandardResultsPagination


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
