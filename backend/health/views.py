"""
Student health records.

Who sees what:
- view_health_records: read every student's health information (teachers get this by default).
- manage_health_records: also edit it and record incidents (a nurse or the office).
- A linked parent: reads their own child's information and incidents. The student does not.
Every change is written to the audit log.
"""
from django.shortcuts import get_object_or_404
from rest_framework import serializers, status
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.audit import log_action
from core.pagination import StandardResultsPagination
from core.query_params import date_param, uuid_param
from roles.permissions import HasPermission

from .models import INCIDENT_KIND_CHOICES, HealthIncident, StudentHealthProfile

PROFILE_FIELDS = ["allergies", "medical_conditions", "medications", "dietary_notes", "doctor_name", "doctor_phone", "notes"]


def _can(request, codename):
    return HasPermission(codename).has_permission(request, None)


def _is_parent_of(request, student):
    from fees.services import get_child_for_parent, get_parent_for_user

    parent = get_parent_for_user(request.user)
    return parent is not None and get_child_for_parent(parent, student.id) is not None


def _staff(request):
    from fees.services import get_staff_member_for_user

    return get_staff_member_for_user(request.user)


def _check_read(request, student):
    if _can(request, "view_health_records") or _can(request, "manage_health_records") or _is_parent_of(request, student):
        return
    raise PermissionDenied("You cannot see this student's health information.")


def _check_manage(request):
    if not _can(request, "manage_health_records"):
        raise PermissionDenied("You cannot change health records.")


def _name(student):
    p = student.profile
    return f"{p.first_name} {p.last_name}".strip()


class HealthProfileSerializer(serializers.ModelSerializer):
    blood_group = serializers.CharField(source="student.profile.blood_group", read_only=True)
    has_alert = serializers.BooleanField(read_only=True)

    class Meta:
        model = StudentHealthProfile
        fields = ["student", *PROFILE_FIELDS, "blood_group", "has_alert", "updated_at"]
        read_only_fields = ["student", "updated_at"]


class HealthIncidentSerializer(serializers.ModelSerializer):
    student_name = serializers.SerializerMethodField()
    kind_display = serializers.CharField(source="get_kind_display", read_only=True)
    recorded_by_name = serializers.SerializerMethodField()

    class Meta:
        model = HealthIncident
        fields = [
            "id", "student", "student_name", "occurred_at", "kind", "kind_display", "description", "action_taken",
            "sent_home", "parent_informed", "recorded_by_name", "created_at",
        ]
        read_only_fields = ["id", "student", "created_at"]

    def get_student_name(self, obj):
        return _name(obj.student)

    def get_recorded_by_name(self, obj):
        staff = obj.recorded_by
        if staff is None:
            return None
        p = staff.profile
        return f"{p.first_name} {p.last_name}".strip()

    def validate_description(self, value):
        if not value.strip():
            raise serializers.ValidationError("Say what happened.")
        return value.strip()


def _student(student_id):
    from students.models import Student

    return get_object_or_404(Student.objects.select_related("profile"), id=student_id)


class StudentHealthView(APIView):
    """GET /api/health-records/students/<id>/ - the profile and recent incidents.
    PUT  same URL - save the profile (manage_health_records)."""

    permission_classes = [IsAuthenticated]

    def get(self, request, student_id):
        student = _student(student_id)
        _check_read(request, student)
        profile = StudentHealthProfile.objects.filter(student=student).first() or StudentHealthProfile(student=student)
        incidents = student.health_incidents.select_related("student__profile", "recorded_by__profile")[:50]
        return Response({
            "student": str(student.id),
            "student_name": _name(student),
            "profile": HealthProfileSerializer(profile).data,
            "incidents": HealthIncidentSerializer(incidents, many=True).data,
            "can_manage": _can(request, "manage_health_records"),
        })

    def put(self, request, student_id):
        _check_manage(request)
        student = _student(student_id)
        profile, _ = StudentHealthProfile.objects.get_or_create(student=student)
        before = {f: getattr(profile, f) for f in PROFILE_FIELDS}
        serializer = HealthProfileSerializer(profile, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        profile = serializer.save(updated_by=_staff(request))
        changed = [f for f in PROFILE_FIELDS if getattr(profile, f) != before[f]]
        if changed:
            # Field names only: the audit log is wider-read than health records.
            log_action(request, action="health_profile_updated", model_name="StudentHealthProfile",
                       object_id=profile.id, changes={"student": str(student.id), "fields": changed})
        return Response(HealthProfileSerializer(profile).data)


class StudentIncidentsView(APIView):
    """POST /api/health-records/students/<id>/incidents/ - record an incident (manage_health_records)."""

    permission_classes = [IsAuthenticated]

    def post(self, request, student_id):
        _check_manage(request)
        student = _student(student_id)
        serializer = HealthIncidentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        incident = serializer.save(student=student, recorded_by=_staff(request))
        log_action(request, action="health_incident_recorded", model_name="HealthIncident", object_id=incident.id,
                   changes={"student": str(student.id), "kind": incident.kind})
        return Response(HealthIncidentSerializer(incident).data, status=status.HTTP_201_CREATED)


class IncidentDetailView(APIView):
    """PATCH /api/health-records/incidents/<id>/ - add follow-up, such as the parent now informed."""

    permission_classes = [IsAuthenticated]

    def patch(self, request, incident_id):
        _check_manage(request)
        incident = get_object_or_404(HealthIncident.objects.select_related("student__profile"), id=incident_id)
        serializer = HealthIncidentSerializer(incident, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        incident = serializer.save()
        log_action(request, action="health_incident_updated", model_name="HealthIncident", object_id=incident.id,
                   changes={"fields": sorted(serializer.validated_data)})
        return Response(HealthIncidentSerializer(incident).data)


class IncidentLogView(APIView):
    """GET /api/health-records/incidents/?from=&to=&student= - the school's incident log, newest first."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not (_can(request, "view_health_records") or _can(request, "manage_health_records")):
            raise PermissionDenied("You cannot see health records.")
        qs = HealthIncident.objects.select_related("student__profile", "recorded_by__profile")
        start, end = date_param(request, "from"), date_param(request, "to")
        student = uuid_param(request, "student")
        if start:
            qs = qs.filter(occurred_at__date__gte=start)
        if end:
            qs = qs.filter(occurred_at__date__lte=end)
        if student:
            qs = qs.filter(student_id=student)
        paginator = StandardResultsPagination()
        page = paginator.paginate_queryset(qs, request, view=self)
        return paginator.get_paginated_response(HealthIncidentSerializer(page, many=True).data)


class HealthAlertsView(APIView):
    """GET /api/health-records/alerts/?section=<id> - students with an allergy or condition,
    so a teacher can see them for a class at a glance."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not (_can(request, "view_health_records") or _can(request, "manage_health_records")):
            raise PermissionDenied("You cannot see health records.")
        from django.db.models import Q

        qs = (
            StudentHealthProfile.objects.filter(student__status="active")
            .exclude(Q(allergies="") & Q(medical_conditions=""))
            .select_related("student__profile")
        )
        section = uuid_param(request, "section")
        if section:
            qs = qs.filter(student__enrollments__is_current=True, student__enrollments__section_id=section).distinct()
        rows = sorted(qs, key=lambda p: _name(p.student).lower())
        return Response([
            {
                "student": str(p.student_id), "student_name": _name(p.student),
                "allergies": p.allergies, "medical_conditions": p.medical_conditions, "medications": p.medications,
            }
            for p in rows if p.has_alert
        ])


INCIDENT_KINDS = [{"value": v, "label": label} for v, label in INCIDENT_KIND_CHOICES]
