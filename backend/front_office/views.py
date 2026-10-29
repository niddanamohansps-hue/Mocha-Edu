from django.db.models import Q
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from roles.permissions import HasPermission
from .models import VisitorLog, StudentGatePass, PostalRecord
from .serializers import (
    VisitorLogSerializer,
    StudentGatePassSerializer,
    PostalRecordSerializer,
)
from .services import get_front_office_overview


class VisitorLogViewSet(viewsets.ModelViewSet):
    serializer_class = VisitorLogSerializer

    def get_permissions(self):
        if self.action in ["create", "update", "partial_update", "destroy", "check_out"]:
            return [IsAuthenticated(), HasPermission("manage_visitors")()]
        return [IsAuthenticated(), HasPermission("view_front_office")()]

    def get_queryset(self):
        qs = VisitorLog.objects.select_related(
            "person_to_meet_staff",
            "person_to_meet_staff__profile",
            "student",
            "student__profile",
        ).all()
        params = self.request.query_params

        status_param = params.get("status")
        if status_param:
            qs = qs.filter(status=status_param)

        date_param = params.get("date")
        if date_param:
            qs = qs.filter(check_in_time__date=date_param)

        search = params.get("search")
        if search:
            qs = qs.filter(
                Q(pass_number__icontains=search)
                | Q(visitor_name__icontains=search)
                | Q(phone__icontains=search)
                | Q(badge_number__icontains=search)
                | Q(vehicle_number__icontains=search)
                | Q(organization__icontains=search)
            )

        return qs

    @action(detail=True, methods=["post"])
    def check_out(self, request, pk=None):
        visitor = self.get_object()
        if visitor.status == VisitorLog.Status.CHECKED_OUT:
            return Response({"detail": "Visitor has already checked out."}, status=status.HTTP_400_BAD_REQUEST)

        visitor.status = VisitorLog.Status.CHECKED_OUT
        visitor.check_out_time = timezone.now()
        remarks = request.data.get("remarks")
        if remarks:
            visitor.remarks = f"{visitor.remarks}\nExit note: {remarks}".strip()
        visitor.save(update_fields=["status", "check_out_time", "remarks", "updated_at"])

        return Response(VisitorLogSerializer(visitor).data)


class StudentGatePassViewSet(viewsets.ModelViewSet):
    serializer_class = StudentGatePassSerializer

    def get_permissions(self):
        if self.action in ["create", "update", "partial_update", "destroy", "confirm_exit", "cancel"]:
            return [IsAuthenticated(), HasPermission("issue_gate_pass")()]
        return [IsAuthenticated(), HasPermission("view_front_office")()]

    def get_queryset(self):
        qs = StudentGatePass.objects.select_related(
            "student",
            "student__profile",
            "authorized_by_staff",
            "authorized_by_staff__profile",
        ).all()
        params = self.request.query_params

        status_param = params.get("status")
        if status_param:
            qs = qs.filter(status=status_param)

        date_param = params.get("date")
        if date_param:
            qs = qs.filter(departure_date=date_param)

        student_id = params.get("student")
        if student_id:
            qs = qs.filter(student_id=student_id)

        search = params.get("search")
        if search:
            qs = qs.filter(
                Q(pass_number__icontains=search)
                | Q(student__enrollment_id__icontains=search)
                | Q(student__profile__first_name__icontains=search)
                | Q(student__profile__last_name__icontains=search)
                | Q(picked_up_by_name__icontains=search)
                | Q(picked_up_by_phone__icontains=search)
            )

        return qs

    @action(detail=True, methods=["post"])
    def confirm_exit(self, request, pk=None):
        gp = self.get_object()
        if gp.status == StudentGatePass.Status.DEPARTED:
            return Response({"detail": "Student has already departed."}, status=status.HTTP_400_BAD_REQUEST)
        if gp.status == StudentGatePass.Status.CANCELLED:
            return Response({"detail": "Cancelled gate passes cannot be exited."}, status=status.HTTP_400_BAD_REQUEST)

        gp.status = StudentGatePass.Status.DEPARTED
        gp.actual_exit_time = timezone.now()
        guard_note = request.data.get("gate_security_note")
        if guard_note:
            gp.gate_security_note = guard_note
        gp.save(update_fields=["status", "actual_exit_time", "gate_security_note", "updated_at"])

        return Response(StudentGatePassSerializer(gp).data)

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        gp = self.get_object()
        if gp.status == StudentGatePass.Status.DEPARTED:
            return Response({"detail": "Cannot cancel a gate pass after student departure."}, status=status.HTTP_400_BAD_REQUEST)

        gp.status = StudentGatePass.Status.CANCELLED
        note = request.data.get("reason", "Cancelled by authorized staff")
        gp.gate_security_note = f"Cancelled: {note}"
        gp.save(update_fields=["status", "gate_security_note", "updated_at"])

        return Response(StudentGatePassSerializer(gp).data)


class PostalRecordViewSet(viewsets.ModelViewSet):
    serializer_class = PostalRecordSerializer

    def get_permissions(self):
        if self.action in ["create", "update", "partial_update", "destroy"]:
            return [IsAuthenticated(), HasPermission("manage_postal_records")()]
        return [IsAuthenticated(), HasPermission("view_front_office")()]

    def get_queryset(self):
        qs = PostalRecord.objects.select_related("recipient_staff", "recipient_staff__profile").all()
        params = self.request.query_params

        record_type = params.get("record_type")
        if record_type:
            qs = qs.filter(record_type=record_type)

        date_param = params.get("date")
        if date_param:
            qs = qs.filter(dispatch_date=date_param)

        search = params.get("search")
        if search:
            qs = qs.filter(
                Q(tracking_number__icontains=search)
                | Q(title__icontains=search)
                | Q(from_title__icontains=search)
                | Q(to_title__icontains=search)
                | Q(courier_company__icontains=search)
                | Q(reference_number__icontains=search)
            )

        return qs


class FrontOfficeOverviewView(APIView):
    def get_permissions(self):
        return [IsAuthenticated(), HasPermission("view_front_office")()]

    def get(self, request):
        stats = get_front_office_overview()
        return Response(stats)

