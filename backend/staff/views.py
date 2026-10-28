from rest_framework import viewsets, permissions, status
from rest_framework.views import APIView
from rest_framework.response import Response
from core.pagination import StandardResultsPagination
from .models import StaffMember, Instructor
from .serializers import (
    StaffMemberSerializer,
    InstructorSerializer,
    InstructorOnboardingSerializer,
    InstructorDetailSerializer,
)
from roles.permissions import HasPermission
from accounts.utils.crypto import decrypt_secret
from core.audit import log_action


class StaffMemberViewSet(viewsets.ModelViewSet):
    queryset = StaffMember.objects.all().select_related(
        "profile", "profile__student_record", "instructor_record"
    ).order_by(
        "profile__first_name", "profile__last_name"
    )
    serializer_class = StaffMemberSerializer
    pagination_class = StandardResultsPagination

    def get_permissions(self):
        if self.action in ["list", "retrieve"]:
            return [permissions.IsAuthenticated(), HasPermission("view_staff")]
        if self.action == "create":
            return [permissions.IsAuthenticated(), HasPermission("add_staff")]
        if self.action in ["update", "partial_update"]:
            return [permissions.IsAuthenticated(), HasPermission("change_staff")]
        if self.action == "destroy":
            return [permissions.IsAuthenticated(), HasPermission("delete_staff")]
        return [permissions.IsAuthenticated(), HasPermission("view_staff")]

    def get_serializer_class(self):
        if self.action in ["update", "partial_update"]:
            from .serializers import StaffMemberUpdateSerializer

            return StaffMemberUpdateSerializer
        return StaffMemberSerializer

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        # Optional bounded server-side narrowing (used by pickers).
        from django.db.models import Q

        for term in (request.query_params.get("search") or "").split()[:5]:
            queryset = queryset.filter(
                Q(profile__first_name__icontains=term)
                | Q(profile__last_name__icontains=term)
                | Q(employee_id__icontains=term)
            )
        active = request.query_params.get("is_active")
        if active in ("true", "false"):
            queryset = queryset.filter(is_active=(active == "true"))

        page = self.paginate_queryset(queryset)
        if page is not None:
            self._prefetch_users(page)
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        self._prefetch_users(queryset)
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    def _prefetch_users(self, staff_list):
        """
        Manually fetch global users and attach them to profiles
        to prevent N+1 queries during serialization.
        """
        from django.apps import apps

        User = apps.get_model("accounts", "User")

        # Collect IDs
        user_ids = [s.profile.user_id for s in staff_list if s.profile.user_id]

        if not user_ids:
            return

        # Bulk fetch
        users = User.objects.filter(id__in=user_ids)
        user_map = {u.id: u for u in users}

        # Attach to instances
        for staff in staff_list:
            if staff.profile.user_id in user_map:
                staff.profile._user_cache = user_map[staff.profile.user_id]


class InstructorViewSet(viewsets.ModelViewSet):
    queryset = Instructor.objects.all().select_related("staff_member__profile").order_by(
        "staff_member__profile__first_name", "staff_member__profile__last_name"
    )
    serializer_class = InstructorDetailSerializer
    pagination_class = StandardResultsPagination

    def get_permissions(self):
        if self.action in ["list", "retrieve"]:
            return [permissions.IsAuthenticated(), HasPermission("view_staff")]
        if self.action == "create":
            return [permissions.IsAuthenticated(), HasPermission("add_staff")]
        if self.action in ["update", "partial_update"]:
            return [permissions.IsAuthenticated(), HasPermission("change_staff")]
        if self.action == "destroy":
            return [permissions.IsAuthenticated(), HasPermission("delete_staff")]
        return [permissions.IsAuthenticated(), HasPermission("view_staff")]

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())

        page = self.paginate_queryset(queryset)
        if page is not None:
            self._prefetch_users(page)
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        self._prefetch_users(queryset)
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    def _prefetch_users(self, instructor_list):
        from django.apps import apps

        User = apps.get_model("accounts", "User")

        # Access chain: Instructor -> StaffMember -> Profile -> UserID
        user_ids = [
            i.staff_member.profile.user_id
            for i in instructor_list
            if i.staff_member.profile.user_id
        ]

        if not user_ids:
            return

        users = User.objects.filter(id__in=user_ids)
        user_map = {u.id: u for u in users}

        for instructor in instructor_list:
            pid = instructor.staff_member.profile.user_id
            if pid in user_map:
                instructor.staff_member.profile._user_cache = user_map[pid]


class InstructorOnboardingView(APIView):
    """
    Phase 1: 'Hiring' an Instructor.
    Creates a Profile and Staff/Instructor record without a User login.
    """

    permission_classes = [permissions.IsAuthenticated, HasPermission("add_staff")]

    def post(self, request):
        serializer = InstructorOnboardingSerializer(data=request.data)
        if serializer.is_valid():
            instructor = serializer.save()
            return Response(
                {
                    "message": "Instructor onboarded successfully",
                    "instructor_id": instructor.id,
                    "staff_id": instructor.staff_member.id,
                    "employee_id": instructor.staff_member.employee_id,
                    "name": f"{instructor.staff_member.profile.first_name} {instructor.staff_member.profile.last_name}",
                },
                status=status.HTTP_201_CREATED,
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class InstructorActivationView(APIView):
    """
    Phase 2: 'IT Access'.
    Creates a User account for an existing Instructor/Staff member.
    """

    permission_classes = [
        permissions.IsAuthenticated,
        HasPermission("activate_staff_portal"),
    ]

    def post(self, request):
        serializer = InstructorActivationSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            return Response(
                {
                    "message": "Instructor account activated successfully",
                    "username": user.username,  # This might be the global one, usually we want the local one
                    # But the serializer returns the User object.
                    # We can fetch local_username from the profile if needed,
                    # but typically the user just needs to know it worked.
                },
                status=status.HTTP_201_CREATED,
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class CredentialDistributionView(APIView):
    """
    Phase 3: 'Distribution'.
    Lists staff/instructors who have been activated but haven't changed their password.
    Includes their initial temporary password.
    Optimized to prevent N+1 queries.
    """

    permission_classes = [permissions.IsAuthenticated, HasPermission("view_staff")]

    def get(self, request):
        from django.apps import apps

        User = apps.get_model("accounts", "User")

        # 1. Fetch Staff
        staff_members = StaffMember.objects.filter(
            profile__user_id__isnull=False
        ).select_related("profile")

        # 2. Collect User IDs
        user_ids = [s.profile.user_id for s in staff_members if s.profile.user_id]

        if not user_ids:
            return Response([])

        # 3. Bulk Fetch Users (1 Query)
        users = User.objects.filter(id__in=user_ids)
        user_map = {u.id: u for u in users}

        data = []
        for s in staff_members:
            user = user_map.get(s.profile.user_id)

            # Check if user exists and needs password change
            if user and user.needs_password_change and user.initial_password_display:
                data.append(
                    {
                        "id": s.id,
                        "full_name": f"{s.profile.first_name} {s.profile.last_name}",
                        "employee_id": s.employee_id,
                        "username": s.profile.local_username or user.username,
                        "initial_password": decrypt_secret(user.initial_password_display),
                        "designation": s.designation,
                    }
                )

        if data:
            log_action(
                request,
                action="credentials_viewed",
                model_name="StaffMember",
                object_id=",".join(str(d["id"]) for d in data),
            )

        return Response(data)


class StaffOnboardingView(APIView):
    """
    Phase 1: 'Hiring' a General Staff Member.
    Creates a Profile and StaffMember record without a User login.
    """

    permission_classes = [permissions.IsAuthenticated, HasPermission("add_staff")]

    def post(self, request):
        from .serializers import StaffOnboardingSerializer

        serializer = StaffOnboardingSerializer(data=request.data)
        if serializer.is_valid():
            staff = serializer.save()
            return Response(
                {
                    "message": "Staff member onboarded successfully",
                    "staff_id": staff.id,
                    "employee_id": staff.employee_id,
                    "name": f"{staff.profile.first_name} {staff.profile.last_name}",
                    "designation": staff.designation,
                },
                status=status.HTTP_201_CREATED,
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class StaffActivationView(APIView):
    """
    Phase 2: 'IT Access' for General Staff.
    Creates a User account for an existing Staff member and assigns a Role.
    """

    permission_classes = [
        permissions.IsAuthenticated,
        HasPermission("activate_staff_portal"),
    ]

    def post(self, request):
        from .serializers import StaffActivationSerializer

        serializer = StaffActivationSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            return Response(
                {
                    "message": "Staff account activated successfully",
                    "username": user.username,
                },
                status=status.HTTP_201_CREATED,
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
