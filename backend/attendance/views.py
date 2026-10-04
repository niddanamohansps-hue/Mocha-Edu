from django.db.models import Count
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.audit import log_action
from roles.permissions import HasPermission

from .models import AttendanceSession, AttendanceSettings, StaffAttendance, StudentAttendance
from .serializers import (
    AttendanceSessionBulkSerializer,
    AttendanceSessionSerializer,
    AttendanceSessionUpdateSerializer,
    AttendanceSettingsSerializer,
    LockedSessionError,
    StaffAttendanceBulkSerializer,
    StaffAttendanceSerializer,
    StudentAttendanceSerializer,
)
from .services import (
    calculate_attendance_percentage,
    get_section_roster,
    get_staff_member_for_user,
    get_student_for_user,
    user_can_access_section,
    user_can_access_student_attendance,
)


class SectionRosterView(APIView):
    permission_classes = [IsAuthenticated, HasPermission("view_attendance")]

    def get(self, request, section_id):
        if not user_can_access_section(request, section_id):
            return Response(
                {"error": "You are not assigned to this section."},
                status=status.HTTP_403_FORBIDDEN,
            )

        target_date = request.query_params.get("date") or timezone.localdate().isoformat()

        roster = get_section_roster(section_id)
        # prefetch_related (not select_related) on the reverse student_records
        # relation, with student__profile nested inside it - both are
        # forward, single-valued relations (FK then O2O), so this can never
        # duplicate rows. Using prefetch_related HERE, on the session fetch
        # itself, rather than only on the local `session.student_records`
        # access below, is required: AttendanceSessionSerializer (used for
        # this same response's "session" field) ALSO serializes
        # `student_records` via its own nested StudentAttendanceSerializer,
        # through a SEPARATE `session.student_records.all()` call Django
        # resolves independently. Explicitly chaining `.select_related(...)`
        # on only ONE of those two access points creates a fresh queryset
        # that bypasses any prefetch cache, so the other access point still
        # re-triggers the N+1 (confirmed via direct SQL inspection - see
        # Phase 9F report). Prefetching on `session` itself populates one
        # shared cache that both `session.student_records.all()` calls -
        # the one below AND the one inside AttendanceSessionSerializer -
        # read from, with zero additional queries either way.
        session = (
            AttendanceSession.objects.filter(section_id=section_id, date=target_date)
            .prefetch_related("student_records__student__profile")
            .first()
        )

        existing_by_student = {}
        if session:
            # Bare `.all()` - NOT `.select_related(...)` - so this reads
            # from the prefetch cache populated above instead of issuing a
            # fresh, unoptimized query (see the comment above `session =`).
            existing_by_student = {
                str(r.student_id): StudentAttendanceSerializer(r).data
                for r in session.student_records.all()
            }

        students = []
        for student in roster:
            students.append(
                {
                    "student": str(student.id),
                    "full_name": f"{student.profile.first_name} {student.profile.last_name}",
                    "enrollment_id": student.enrollment_id,
                    "existing": existing_by_student.get(str(student.id)),
                }
            )

        return Response(
            {
                "date": target_date,
                "section": str(section_id),
                "session": AttendanceSessionSerializer(session).data if session else None,
                "students": students,
            }
        )


class AttendanceSessionViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]

    def get_permissions(self):
        if self.action == "create":
            perm = HasPermission("mark_attendance")
        elif self.action == "partial_update":
            perm = HasPermission("change_attendance")
        elif self.action == "destroy":
            perm = HasPermission("delete_attendance_session")
        elif self.action == "lock":
            perm = HasPermission("lock_attendance")
        else:
            perm = HasPermission("view_attendance")
        return [IsAuthenticated(), perm]

    def _get_session_or_403(self, request, pk):
        session = get_object_or_404(AttendanceSession, pk=pk)
        if not user_can_access_section(request, session.section_id):
            return None, Response(
                {"error": "You are not assigned to this section."},
                status=status.HTTP_403_FORBIDDEN,
            )
        return session, None

    def retrieve(self, request, pk=None):
        session, error = self._get_session_or_403(request, pk)
        if error:
            return error
        return Response(AttendanceSessionSerializer(session).data)

    def create(self, request):
        serializer = AttendanceSessionBulkSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        section_id = serializer.validated_data["section_obj"].id
        if not user_can_access_section(request, section_id):
            return Response(
                {"error": "You are not assigned to this section."},
                status=status.HTTP_403_FORBIDDEN,
            )

        recorded_by = get_staff_member_for_user(request.user)

        try:
            session, created, change_summary = serializer.save(
                request=request, recorded_by=recorded_by
            )
        except LockedSessionError as exc:
            return Response(
                {"error": "This attendance session is locked."},
                status=status.HTTP_423_LOCKED,
            )

        log_action(
            request,
            action="attendance_marked" if created else "attendance_modified",
            model_name="AttendanceSession",
            object_id=session.id,
            changes={
                "section": str(session.section_id),
                "date": str(session.date),
                "counts": change_summary["counts"],
                **({"changed": change_summary["changed"]} if change_summary["changed"] else {}),
            },
        )

        return Response(
            AttendanceSessionSerializer(session).data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )

    def partial_update(self, request, pk=None):
        session, error = self._get_session_or_403(request, pk)
        if error:
            return error

        serializer = AttendanceSessionUpdateSerializer(data=request.data, session=session)
        serializer.is_valid(raise_exception=True)

        recorded_by = get_staff_member_for_user(request.user)

        try:
            session, change_summary = serializer.save(request=request, recorded_by=recorded_by)
        except LockedSessionError:
            return Response(
                {"error": "This attendance session is locked."},
                status=status.HTTP_423_LOCKED,
            )

        log_action(
            request,
            action="attendance_modified",
            model_name="AttendanceSession",
            object_id=session.id,
            changes={
                "section": str(session.section_id),
                "date": str(session.date),
                "counts": change_summary["counts"],
                "changed": change_summary["changed"],
            },
        )

        return Response(AttendanceSessionSerializer(session).data)

    def destroy(self, request, pk=None):
        session, error = self._get_session_or_403(request, pk)
        if error:
            return error

        session_id, section_id, session_date = session.id, session.section_id, session.date
        record_count = session.student_records.count()
        session.delete()

        log_action(
            request,
            action="attendance_session_deleted",
            model_name="AttendanceSession",
            object_id=session_id,
            changes={
                "section": str(section_id),
                "date": str(session_date),
                "records_deleted": record_count,
            },
        )
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=["post"])
    def lock(self, request, pk=None):
        session, error = self._get_session_or_403(request, pk)
        if error:
            return error

        lock_value = request.data.get("is_locked", True)
        session.is_locked = bool(lock_value)
        session.locked_at = timezone.now() if session.is_locked else None
        session.save(update_fields=["is_locked", "locked_at", "updated_at"])

        log_action(
            request,
            action="attendance_locked" if session.is_locked else "attendance_unlocked",
            model_name="AttendanceSession",
            object_id=session.id,
            changes={"section": str(session.section_id), "date": str(session.date)},
        )
        return Response(AttendanceSessionSerializer(session).data)


class StudentAttendanceHistoryView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, student_id):
        from students.models import Student

        student = get_object_or_404(Student.objects.select_related("profile"), id=student_id)

        # A student may always read their own; anyone else needs the permission
        # AND (if an instructor) section-scoped access to this specific student.
        own_student = get_student_for_user(request.user)
        if own_student is None or own_student.id != student.id:
            if not HasPermission("view_attendance").has_permission(request, None):
                return Response(
                    {"error": "You do not have permission to view attendance."},
                    status=status.HTTP_403_FORBIDDEN,
                )
            if not user_can_access_student_attendance(request, student):
                return Response(
                    {"error": "You are not authorized to view this student's attendance."},
                    status=status.HTTP_403_FORBIDDEN,
                )

        qs = StudentAttendance.objects.filter(student=student).select_related("session")
        start_date = request.query_params.get("start_date")
        end_date = request.query_params.get("end_date")
        if start_date:
            qs = qs.filter(session__date__gte=start_date)
        if end_date:
            qs = qs.filter(session__date__lte=end_date)
        qs = qs.order_by("-session__date")

        counts = {}
        for row in qs:
            counts[row.status] = counts.get(row.status, 0) + 1

        settings_obj = AttendanceSettings.get_solo()
        percentage = calculate_attendance_percentage(counts, settings_obj)

        return Response(
            {
                "student": str(student.id),
                "counts": counts,
                "percentage": percentage,
                "records": [
                    {
                        "date": r.session.date,
                        "status": r.status,
                        "remarks": r.remarks,
                    }
                    for r in qs
                ],
            }
        )


class SectionAttendanceSummaryView(APIView):
    permission_classes = [IsAuthenticated, HasPermission("view_attendance")]

    def get(self, request, section_id):
        if not user_can_access_section(request, section_id):
            return Response(
                {"error": "You are not assigned to this section."},
                status=status.HTTP_403_FORBIDDEN,
            )

        qs = StudentAttendance.objects.filter(session__section_id=section_id)
        month = request.query_params.get("month")
        year = request.query_params.get("year")
        if year:
            qs = qs.filter(session__date__year=year)
        if month:
            qs = qs.filter(session__date__month=month)

        counts = dict(qs.values_list("status").annotate(total=Count("id")))
        settings_obj = AttendanceSettings.get_solo()
        percentage = calculate_attendance_percentage(counts, settings_obj)

        return Response({"section": str(section_id), "counts": counts, "percentage": percentage})


class BelowThresholdReportView(APIView):
    permission_classes = [IsAuthenticated, HasPermission("view_attendance_reports")]

    def get(self, request):
        section_id = request.query_params.get("section")
        academic_year = request.query_params.get("academic_year")

        if section_id and not user_can_access_section(request, section_id):
            return Response(
                {"error": "You are not assigned to this section."},
                status=status.HTTP_403_FORBIDDEN,
            )

        qs = StudentAttendance.objects.select_related("student__profile", "session")
        if section_id:
            qs = qs.filter(session__section_id=section_id)
        if academic_year:
            qs = qs.filter(session__academic_year=academic_year)

        settings_obj = AttendanceSettings.get_solo()
        threshold = float(settings_obj.minimum_attendance_percentage)

        per_student = {}
        for row in qs:
            per_student.setdefault(row.student_id, {"student": row.student, "counts": {}})
            per_student[row.student_id]["counts"][row.status] = (
                per_student[row.student_id]["counts"].get(row.status, 0) + 1
            )

        results = []
        for entry in per_student.values():
            pct = calculate_attendance_percentage(entry["counts"], settings_obj)
            if pct is not None and pct < threshold:
                student = entry["student"]
                results.append(
                    {
                        "student": str(student.id),
                        "full_name": f"{student.profile.first_name} {student.profile.last_name}",
                        "enrollment_id": student.enrollment_id,
                        "percentage": pct,
                    }
                )

        return Response({"threshold": threshold, "students": results})


class TenantAttendanceSummaryView(APIView):
    permission_classes = [IsAuthenticated, HasPermission("view_attendance_reports")]

    def get(self, request):
        target_date = request.query_params.get("date") or timezone.localdate().isoformat()

        counts = dict(
            StudentAttendance.objects.filter(session__date=target_date)
            .values_list("status")
            .annotate(total=Count("id"))
        )
        settings_obj = AttendanceSettings.get_solo()
        percentage = calculate_attendance_percentage(counts, settings_obj)

        return Response({"date": target_date, "counts": counts, "percentage": percentage})


class StaffAttendanceBulkView(APIView):
    permission_classes = [IsAuthenticated, HasPermission("mark_staff_attendance")]

    def post(self, request):
        serializer = StaffAttendanceBulkSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        recorded_by = get_staff_member_for_user(request.user)
        results = serializer.save(recorded_by=recorded_by)

        counts = {}
        for r in results:
            counts[r.status] = counts.get(r.status, 0) + 1

        log_action(
            request,
            action="staff_attendance_marked",
            model_name="StaffAttendance",
            object_id=str(serializer.validated_data["date"]),
            changes={"date": str(serializer.validated_data["date"]), "counts": counts},
        )

        return Response(
            StaffAttendanceSerializer(results, many=True).data, status=status.HTTP_200_OK
        )


class StaffAttendanceHistoryView(APIView):
    permission_classes = [IsAuthenticated, HasPermission("view_staff_attendance")]

    def get(self, request, staff_id):
        qs = StaffAttendance.objects.filter(staff_id=staff_id).order_by("-date")
        start_date = request.query_params.get("start_date")
        end_date = request.query_params.get("end_date")
        if start_date:
            qs = qs.filter(date__gte=start_date)
        if end_date:
            qs = qs.filter(date__lte=end_date)

        counts = {}
        for row in qs:
            counts[row.status] = counts.get(row.status, 0) + 1

        settings_obj = AttendanceSettings.get_solo()
        percentage = calculate_attendance_percentage(counts, settings_obj)

        return Response(
            {
                "staff": str(staff_id),
                "counts": counts,
                "percentage": percentage,
                "records": StaffAttendanceSerializer(qs, many=True).data,
            }
        )


class AttendanceSettingsView(APIView):
    def get_permissions(self):
        perm = HasPermission(
            "view_institution_profile" if self.request.method == "GET" else "change_institution_profile"
        )
        return [IsAuthenticated(), perm]

    def get(self, request):
        return Response(AttendanceSettingsSerializer(AttendanceSettings.get_solo()).data)

    def patch(self, request):
        instance = AttendanceSettings.get_solo()
        old_weights = dict(instance.status_weights)
        serializer = AttendanceSettingsSerializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        updated = serializer.save()

        log_action(
            request,
            action="attendance_settings_changed",
            model_name="AttendanceSettings",
            object_id=updated.id,
            changes={"old_status_weights": old_weights, "new_status_weights": updated.status_weights},
        )
        return Response(AttendanceSettingsSerializer(updated).data)
