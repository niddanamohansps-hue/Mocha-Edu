from django.db import transaction
from rest_framework import serializers

from .models import (
    ATTENDANCE_STATUS_CHOICES,
    AttendanceSession,
    AttendanceSettings,
    StaffAttendance,
    StudentAttendance,
)
from .services import get_section_roster


class LockedSessionError(Exception):
    def __init__(self, session):
        self.session = session
        super().__init__("This attendance session is locked.")


class StudentAttendanceSerializer(serializers.ModelSerializer):
    student_name = serializers.SerializerMethodField()
    enrollment_id = serializers.CharField(source="student.enrollment_id", read_only=True)

    class Meta:
        model = StudentAttendance
        fields = [
            "id",
            "student",
            "student_name",
            "enrollment_id",
            "status",
            "remarks",
            "recorded_by",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "recorded_by", "created_at", "updated_at"]

    def get_student_name(self, obj):
        profile = obj.student.profile
        return f"{profile.first_name} {profile.last_name}"


class AttendanceSessionSerializer(serializers.ModelSerializer):
    student_records = StudentAttendanceSerializer(many=True, read_only=True)
    section_name = serializers.CharField(source="section.name", read_only=True)

    class Meta:
        model = AttendanceSession
        fields = [
            "id",
            "section",
            "section_name",
            "academic_year",
            "date",
            "recorded_by",
            "is_locked",
            "locked_at",
            "student_records",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "recorded_by",
            "is_locked",
            "locked_at",
            "created_at",
            "updated_at",
        ]


class AttendanceRecordInputSerializer(serializers.Serializer):
    """One student's mark within a bulk session submission."""

    student = serializers.UUIDField()
    status = serializers.ChoiceField(choices=ATTENDANCE_STATUS_CHOICES)
    remarks = serializers.CharField(max_length=255, required=False, allow_blank=True, default="")


class AttendanceSessionBulkSerializer(serializers.Serializer):
    """
    Bulk create/upsert for one section's attendance on one date.
    Validates the whole payload before writing anything, and writes
    everything atomically - a single bad record fails the entire request.
    """

    section = serializers.UUIDField()
    date = serializers.DateField()
    records = AttendanceRecordInputSerializer(many=True)

    def validate(self, attrs):
        from academics.models import Section

        section_id = attrs["section"]
        try:
            section = Section.objects.get(id=section_id)
        except Section.DoesNotExist:
            raise serializers.ValidationError({"section": "Section not found."})
        attrs["section_obj"] = section

        records = attrs["records"]
        if not records:
            raise serializers.ValidationError({"records": "At least one record is required."})

        seen_students = set()
        for record in records:
            student_id = record["student"]
            if student_id in seen_students:
                raise serializers.ValidationError(
                    {"records": f"Duplicate entry for student {student_id} in the same submission."}
                )
            seen_students.add(student_id)

        roster_ids = set(
            str(s) for s in get_section_roster(section_id).values_list("id", flat=True)
        )
        invalid_students = [str(s) for s in seen_students if str(s) not in roster_ids]
        if invalid_students:
            raise serializers.ValidationError(
                {
                    "records": (
                        f"Student(s) {invalid_students} are not currently enrolled "
                        f"in this section - attendance was NOT saved for anyone in this submission."
                    )
                }
            )

        return attrs

    @transaction.atomic
    def save(self, request, recorded_by):
        section = self.validated_data["section_obj"]
        date = self.validated_data["date"]
        records = self.validated_data["records"]

        # Lock this row (or create it) so two concurrent submissions for the
        # same section+date serialize instead of racing to insert duplicates.
        session, created = AttendanceSession.objects.select_for_update().get_or_create(
            section=section,
            date=date,
            defaults={
                "academic_year": self._resolve_academic_year(section),
                "recorded_by": recorded_by,
            },
        )

        if not created and session.is_locked:
            from roles.permissions import HasPermission

            if not HasPermission("edit_locked_attendance").has_permission(request, None):
                raise LockedSessionError(session)

        change_summary = apply_attendance_records(session, records, recorded_by)

        if not created:
            session.recorded_by = recorded_by
            session.save(update_fields=["recorded_by", "updated_at"])

        return session, created, change_summary

    @staticmethod
    def _resolve_academic_year(section):
        """
        The academic year of the section's current enrollment, as recorded on
        StudentLevel. Never derived from the calendar year: a school year like
        "2026-27" must not become "2026" because a session falls in 2026.
        """
        from students.models import StudentLevel

        year = (
            StudentLevel.objects.filter(section_id=section.id, is_current=True)
            .values_list("academic_year", flat=True)
            .first()
        )
        if not year:
            raise serializers.ValidationError(
                {"section": "This section has no current enrollment, so its academic year cannot be determined."}
            )
        return year


def apply_attendance_records(session, records, recorded_by):
    """
    Shared upsert logic used by both the initial bulk POST and subsequent
    PATCH edits, so the two code paths never drift apart.

    Returns a status-count dict of the session's state AFTER applying the
    records (used to build the audit log's `changes` payload), plus the
    list of (student_id, old_status, new_status) changes for edits.
    """
    existing = {
        str(r.student_id): r for r in session.student_records.select_related("student")
    }

    to_create = []
    to_update = []
    changed = []
    for record in records:
        student_id = str(record["student"])
        new_status = record["status"]
        if student_id in existing:
            row = existing[student_id]
            if row.status != new_status:
                changed.append({"student": student_id, "old": row.status, "new": new_status})
            row.status = new_status
            row.remarks = record.get("remarks", "")
            row.recorded_by = recorded_by
            to_update.append(row)
        else:
            to_create.append(
                StudentAttendance(
                    session=session,
                    student_id=student_id,
                    status=new_status,
                    remarks=record.get("remarks", ""),
                    recorded_by=recorded_by,
                )
            )

    if to_create:
        StudentAttendance.objects.bulk_create(to_create)
    if to_update:
        StudentAttendance.objects.bulk_update(
            to_update, ["status", "remarks", "recorded_by", "updated_at"]
        )

    counts = {}
    for row in session.student_records.all():
        counts[row.status] = counts.get(row.status, 0) + 1

    return {"counts": counts, "changed": changed}


class AttendanceSessionUpdateSerializer(serializers.Serializer):
    """Edits records on an already-existing session (PATCH), scoped by the
    session found via the URL - no section/date re-validation needed."""

    records = AttendanceRecordInputSerializer(many=True)

    def __init__(self, *args, session=None, **kwargs):
        self._session = session
        super().__init__(*args, **kwargs)

    def validate_records(self, records):
        if not records:
            raise serializers.ValidationError("At least one record is required.")

        roster_ids = set(
            str(s)
            for s in get_section_roster(self._session.section_id).values_list("id", flat=True)
        )
        seen = set()
        for record in records:
            student_id = str(record["student"])
            if student_id in seen:
                raise serializers.ValidationError(
                    f"Duplicate entry for student {student_id} in the same submission."
                )
            seen.add(student_id)

        invalid = [s for s in seen if s not in roster_ids]
        if invalid:
            raise serializers.ValidationError(
                f"Student(s) {invalid} are not currently enrolled in this section - "
                f"nothing was saved."
            )
        return records

    @transaction.atomic
    def save(self, request, recorded_by):
        from roles.permissions import HasPermission

        if self._session.is_locked and not HasPermission(
            "edit_locked_attendance"
        ).has_permission(request, None):
            raise LockedSessionError(self._session)

        change_summary = apply_attendance_records(
            self._session, self.validated_data["records"], recorded_by
        )
        self._session.recorded_by = recorded_by
        self._session.save(update_fields=["recorded_by", "updated_at"])
        return self._session, change_summary


class StaffAttendanceSerializer(serializers.ModelSerializer):
    staff_name = serializers.SerializerMethodField()

    class Meta:
        model = StaffAttendance
        fields = [
            "id",
            "staff",
            "staff_name",
            "date",
            "status",
            "remarks",
            "recorded_by",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "recorded_by", "created_at", "updated_at"]

    def get_staff_name(self, obj):
        profile = obj.staff.profile
        return f"{profile.first_name} {profile.last_name}"


class StaffAttendanceRecordInputSerializer(serializers.Serializer):
    staff = serializers.UUIDField()
    status = serializers.ChoiceField(choices=ATTENDANCE_STATUS_CHOICES)
    remarks = serializers.CharField(max_length=255, required=False, allow_blank=True, default="")


class StaffAttendanceBulkSerializer(serializers.Serializer):
    date = serializers.DateField()
    records = StaffAttendanceRecordInputSerializer(many=True)

    def validate(self, attrs):
        records = attrs["records"]
        if not records:
            raise serializers.ValidationError({"records": "At least one record is required."})

        from staff.models import StaffMember

        seen = set()
        for record in records:
            staff_id = str(record["staff"])
            if staff_id in seen:
                raise serializers.ValidationError(
                    {"records": f"Duplicate entry for staff {staff_id} in the same submission."}
                )
            seen.add(staff_id)

        valid_ids = set(str(s) for s in StaffMember.objects.filter(id__in=seen).values_list("id", flat=True))
        invalid = seen - valid_ids
        if invalid:
            raise serializers.ValidationError(
                {"records": f"Staff member(s) {sorted(invalid)} not found - nothing was saved."}
            )

        return attrs

    @transaction.atomic
    def save(self, recorded_by):
        date = self.validated_data["date"]
        records = self.validated_data["records"]

        results = []
        for record in records:
            obj, _ = StaffAttendance.objects.update_or_create(
                staff_id=record["staff"],
                date=date,
                defaults={
                    "status": record["status"],
                    "remarks": record.get("remarks", ""),
                    "recorded_by": recorded_by,
                },
            )
            results.append(obj)
        return results


class AttendanceSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = AttendanceSettings
        fields = [
            "id",
            "status_weights",
            "minimum_attendance_percentage",
            "lock_after_days",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate_status_weights(self, value):
        instance = AttendanceSettings(status_weights=value)
        instance.clean()
        return value
