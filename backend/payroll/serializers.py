from decimal import Decimal

from django.conf import settings as django_settings
from rest_framework import serializers

from staff.models import StaffMember

from . import services
from .models import PayrollSettings, SalaryComponent, StaffSalary, StaffSalaryComponent


class StrictBooleanField(serializers.BooleanField):
    """Only JSON true/false (DRF's default also accepts "yes", 1, "on", ...)."""

    def to_internal_value(self, data):
        if not isinstance(data, bool):
            self.fail("invalid", input=data)
        return data


def staff_name(staff):
    profile = staff.profile
    return f"{profile.first_name} {profile.last_name}".strip()


class SalaryComponentSerializer(serializers.ModelSerializer):
    assigned_count = serializers.SerializerMethodField()

    class Meta:
        model = SalaryComponent
        fields = ("id", "name", "code", "kind", "calculation", "default_value", "description", "is_active",
                  "sort_order", "assigned_count", "created_at", "updated_at")
        read_only_fields = ("id", "created_at", "updated_at")

    def get_assigned_count(self, component):
        return component.assignments.filter(effective_to__isnull=True).count()

    def validate_code(self, value):
        return value.strip().upper()

    def validate(self, attrs):
        calculation = attrs.get("calculation", getattr(self.instance, "calculation", SalaryComponent.Calculation.FIXED))
        services.validate_component_value(calculation, attrs.get("default_value", getattr(self.instance, "default_value", None)))
        if self.instance is not None and self.instance.assignments.exists():
            for field in ("kind", "calculation"):
                if field in attrs and attrs[field] != getattr(self.instance, field):
                    raise serializers.ValidationError(
                        {field: "This component is already given to staff; its type cannot change. Create a new one."}
                    )
        return attrs


class StaffSalarySerializer(serializers.ModelSerializer):
    staff_name = serializers.SerializerMethodField()
    employee_id = serializers.CharField(source="staff.employee_id", read_only=True)

    class Meta:
        model = StaffSalary
        fields = ("id", "staff", "staff_name", "employee_id", "basic_amount", "effective_from", "note", "created_at")
        read_only_fields = fields

    def get_staff_name(self, salary):
        return staff_name(salary.staff)


class SetSalarySerializer(serializers.Serializer):
    staff = serializers.PrimaryKeyRelatedField(queryset=StaffMember.objects.all())
    basic_amount = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal("0.01"))
    effective_from = serializers.DateField()
    note = serializers.CharField(max_length=255, required=False, allow_blank=True, default="")


class StaffSalaryComponentSerializer(serializers.ModelSerializer):
    component_name = serializers.CharField(source="component.name", read_only=True)
    component_code = serializers.CharField(source="component.code", read_only=True)
    kind = serializers.CharField(source="component.kind", read_only=True)
    calculation = serializers.CharField(source="component.calculation", read_only=True)
    effective_value = serializers.SerializerMethodField()

    class Meta:
        model = StaffSalaryComponent
        fields = ("id", "staff", "component", "component_name", "component_code", "kind", "calculation", "value",
                  "effective_value", "effective_from", "effective_to", "created_at")
        read_only_fields = fields

    def get_effective_value(self, assignment):
        value = assignment.value if assignment.value is not None else assignment.component.default_value
        return f"{value:f}"


class AssignComponentSerializer(serializers.Serializer):
    staff = serializers.PrimaryKeyRelatedField(queryset=StaffMember.objects.all())
    component = serializers.PrimaryKeyRelatedField(queryset=SalaryComponent.objects.all())
    effective_from = serializers.DateField()
    value = serializers.DecimalField(max_digits=12, decimal_places=3, min_value=Decimal("0"), required=False, allow_null=True, default=None)


class EndComponentSerializer(serializers.Serializer):
    effective_to = serializers.DateField()


class PayrollSettingsSerializer(serializers.Serializer):
    """Input: the editable fields (all optional on PATCH; unknown keys and an empty body are rejected).
    Output (``instance=``): the values plus ``is_default`` (nothing saved yet)."""

    round_to_whole_rupee = StrictBooleanField(required=False)
    require_separate_approver = StrictBooleanField(required=False)

    def validate(self, attrs):
        unknown = sorted(set(self.initial_data) - set(PayrollSettings.EDITABLE_FIELDS))
        if unknown:
            raise serializers.ValidationError({"non_field_errors": [f"Unknown or read-only field(s): {', '.join(unknown)}."]})
        if not attrs:
            raise serializers.ValidationError({"non_field_errors": ["No fields supplied."]})
        return attrs

    def to_representation(self, instance):
        data = instance.editable_values()
        data["is_default"] = instance._state.adding
        data["currency"] = getattr(django_settings, "PAYROLL_CURRENCY", "INR")
        return data


def structure_to_dict(structure):
    return {
        "staff": str(structure.staff_id),
        "on_date": structure.on_date.isoformat(),
        "rounded_to_whole_rupee": structure.rounded_to_whole_rupee,
        "lines": [
            {"code": l.code, "name": l.name, "kind": l.kind, "amount": f"{l.amount:f}", "detail": l.detail}
            for l in structure.lines
        ],
        "basic": f"{structure.basic:f}",
        "gross": f"{structure.gross:f}",
        "deductions": f"{structure.deductions:f}",
        "net": f"{structure.net:f}",
        "net_is_negative": structure.net_is_negative,
    }
