"""
EduSekai Staff Leave Management Serializers (Phase 5)
"""

from decimal import Decimal
from rest_framework import serializers

from .models import (
    LeaveApplication,
    LeaveApproval,
    LeaveType,
    StaffLeaveBalance,
    StaffMember,
)


class LeaveTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = LeaveType
        fields = [
            "id",
            "name",
            "code",
            "description",
            "annual_allocation_days",
            "is_paid",
            "requires_document",
            "max_consecutive_days",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate_code(self, value):
        val = value.strip().upper()
        if not val:
            raise serializers.ValidationError("Leave type code cannot be empty.")
        return val


class StaffLeaveBalanceSerializer(serializers.ModelSerializer):
    leave_type_name = serializers.CharField(source="leave_type.name", read_only=True)
    leave_type_code = serializers.CharField(source="leave_type.code", read_only=True)
    is_paid = serializers.BooleanField(source="leave_type.is_paid", read_only=True)
    available_days = serializers.DecimalField(
        max_digits=5, decimal_places=1, read_only=True
    )
    staff_name = serializers.SerializerMethodField()
    employee_id = serializers.CharField(source="staff.employee_id", read_only=True)

    class Meta:
        model = StaffLeaveBalance
        fields = [
            "id",
            "staff",
            "staff_name",
            "employee_id",
            "leave_type",
            "leave_type_name",
            "leave_type_code",
            "is_paid",
            "academic_year",
            "allocated_days",
            "used_days",
            "pending_days",
            "available_days",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "staff",
            "used_days",
            "pending_days",
            "available_days",
            "updated_at",
        ]

    def get_staff_name(self, obj):
        return f"{obj.staff.profile.first_name} {obj.staff.profile.last_name}"


class LeaveApprovalSerializer(serializers.ModelSerializer):
    approver_name = serializers.SerializerMethodField()

    class Meta:
        model = LeaveApproval
        fields = [
            "id",
            "decision",
            "approver",
            "approver_name",
            "comments",
            "decided_at",
        ]
        read_only_fields = ["id", "decided_at"]

    def get_approver_name(self, obj):
        if obj.approver and obj.approver.profile:
            return f"{obj.approver.profile.first_name} {obj.approver.profile.last_name}"
        return "System"


class LeaveApplicationListSerializer(serializers.ModelSerializer):
    staff_name = serializers.SerializerMethodField()
    employee_id = serializers.CharField(source="staff.employee_id", read_only=True)
    leave_type_name = serializers.CharField(source="leave_type.name", read_only=True)
    leave_type_code = serializers.CharField(source="leave_type.code", read_only=True)
    has_document = serializers.SerializerMethodField()

    class Meta:
        model = LeaveApplication
        fields = [
            "id",
            "staff",
            "staff_name",
            "employee_id",
            "leave_type",
            "leave_type_name",
            "leave_type_code",
            "academic_year",
            "start_date",
            "end_date",
            "is_half_day",
            "half_day_session",
            "working_days",
            "reason",
            "status",
            "has_document",
            "applied_at",
        ]
        read_only_fields = fields

    def get_staff_name(self, obj):
        return f"{obj.staff.profile.first_name} {obj.staff.profile.last_name}"

    def get_has_document(self, obj):
        return bool(obj.document)


class LeaveApplicationDetailSerializer(serializers.ModelSerializer):
    staff_name = serializers.SerializerMethodField()
    employee_id = serializers.CharField(source="staff.employee_id", read_only=True)
    department = serializers.CharField(source="staff.department", read_only=True)
    designation = serializers.CharField(source="staff.designation", read_only=True)
    leave_type_name = serializers.CharField(source="leave_type.name", read_only=True)
    leave_type_code = serializers.CharField(source="leave_type.code", read_only=True)
    approvals = LeaveApprovalSerializer(many=True, read_only=True)
    document_url = serializers.SerializerMethodField()

    class Meta:
        model = LeaveApplication
        fields = [
            "id",
            "staff",
            "staff_name",
            "employee_id",
            "department",
            "designation",
            "leave_type",
            "leave_type_name",
            "leave_type_code",
            "academic_year",
            "start_date",
            "end_date",
            "is_half_day",
            "half_day_session",
            "working_days",
            "reason",
            "status",
            "document_name",
            "document_url",
            "approvals",
            "applied_at",
            "updated_at",
        ]
        read_only_fields = fields

    def get_staff_name(self, obj):
        return f"{obj.staff.profile.first_name} {obj.staff.profile.last_name}"

    def get_document_url(self, obj):
        if obj.document:
            return f"/api/staff/leaves/applications/{obj.id}/document/"
        return None


class LeaveApplicationCreateSerializer(serializers.Serializer):
    leave_type_id = serializers.UUIDField()
    start_date = serializers.DateField()
    end_date = serializers.DateField()
    is_half_day = serializers.BooleanField(default=False)
    half_day_session = serializers.ChoiceField(
        choices=[("", "Full Day"), ("morning", "Morning Session"), ("afternoon", "Afternoon Session")],
        default="",
        required=False,
    )
    reason = serializers.CharField(max_length=1000)
    document = serializers.FileField(required=False, allow_null=True)
    academic_year = serializers.CharField(max_length=20, required=False, allow_blank=True)

    def validate(self, attrs):
        if attrs["start_date"] > attrs["end_date"]:
            raise serializers.ValidationError({"end_date": "End date cannot precede start date."})
        if attrs.get("is_half_day") and attrs["start_date"] != attrs["end_date"]:
            raise serializers.ValidationError({"end_date": "Half-day leave must start and end on the same date."})
        return attrs


class LeaveApplicationApproveSerializer(serializers.Serializer):
    comments = serializers.CharField(max_length=500, required=False, allow_blank=True, default="")


class LeaveApplicationRejectSerializer(serializers.Serializer):
    comments = serializers.CharField(max_length=500, required=True)

    def validate_comments(self, value):
        if not value or not value.strip():
            raise serializers.ValidationError("A rejection comment is required.")
        return value.strip()


class LeaveApplicationCancelSerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=500, required=False, allow_blank=True, default="")


class StaffLeaveBalanceAdjustSerializer(serializers.Serializer):
    staff_id = serializers.UUIDField()
    leave_type_id = serializers.UUIDField()
    academic_year = serializers.CharField(max_length=20)
    allocated_days = serializers.DecimalField(max_digits=5, decimal_places=1, min_value=Decimal("0.0"))
    reason = serializers.CharField(max_length=255, required=True)


class AssignSubstitutionSerializer(serializers.Serializer):
    entry_id = serializers.UUIDField()
    date = serializers.DateField()
    substitute_instructor_id = serializers.IntegerField()
    reason = serializers.CharField(max_length=255, required=False, allow_blank=True, default="Staff leave coverage")

