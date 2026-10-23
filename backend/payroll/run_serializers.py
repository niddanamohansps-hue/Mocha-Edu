from decimal import Decimal

from rest_framework import serializers

from staff.models import StaffMember

from .models import PayrollAdjustment, PayrollRun, Payslip, PayslipLine, SalaryComponent

MONTH_NAMES = ["", "January", "February", "March", "April", "May", "June", "July", "August", "September",
               "October", "November", "December"]


def money(value):
    return f"{(value or Decimal('0')):.2f}"


class PayrollRunSerializer(serializers.ModelSerializer):
    month_label = serializers.SerializerMethodField()
    payslip_count = serializers.IntegerField(read_only=True, default=0)
    total_gross = serializers.SerializerMethodField()
    total_deductions = serializers.SerializerMethodField()
    total_net = serializers.SerializerMethodField()

    class Meta:
        model = PayrollRun
        fields = (
            "id", "year", "month", "month_label", "period_start", "period_end", "status", "notes", "working_days",
            "weekly_off_days", "round_to_whole_rupee", "calculation_notes", "payslip_count", "total_gross",
            "total_deductions", "total_net", "created_by_user_id", "prepared_by_user_id", "calculated_at",
            "approved_by_user_id", "approved_at", "paid_on", "paid_by_user_id", "payment_method", "payment_reference",
            "cancelled_at", "cancellation_reason", "created_at", "updated_at",
        )
        read_only_fields = fields

    def get_month_label(self, run):
        return f"{MONTH_NAMES[run.month]} {run.year}"

    # The queryset annotates these sums; a run serialised after an action may not carry them yet.
    def _sum(self, run, field, annotated):
        value = getattr(run, annotated, None)
        if value is None:
            from django.db.models import Sum
            value = run.payslips.aggregate(total=Sum(field))["total"]
        return money(value)

    def get_total_gross(self, run):
        return self._sum(run, "gross_amount", "gross_total")

    def get_total_deductions(self, run):
        return self._sum(run, "deductions_amount", "deductions_total")

    def get_total_net(self, run):
        return self._sum(run, "net_amount", "net_total")


class PayslipLineSerializer(serializers.ModelSerializer):
    class Meta:
        model = PayslipLine
        fields = ("id", "code", "name", "kind", "amount", "detail")
        read_only_fields = fields


class PayslipSerializer(serializers.ModelSerializer):
    net_is_negative = serializers.BooleanField(read_only=True)
    month_label = serializers.SerializerMethodField()
    run_status = serializers.CharField(source="run.status", read_only=True)

    class Meta:
        model = Payslip
        fields = (
            "id", "run", "run_status", "month_label", "staff", "employee_id", "staff_name", "designation", "department",
            "basic_amount", "gross_amount", "deductions_amount", "net_amount", "net_is_negative", "working_days",
            "unpaid_days", "unmarked_days", "created_at",
        )
        read_only_fields = fields

    def get_month_label(self, payslip):
        return f"{MONTH_NAMES[payslip.run.month]} {payslip.run.year}"


class PayslipDetailSerializer(PayslipSerializer):
    lines = PayslipLineSerializer(many=True, read_only=True)

    class Meta(PayslipSerializer.Meta):
        fields = PayslipSerializer.Meta.fields + ("lines",)
        read_only_fields = fields


class PayrollAdjustmentSerializer(serializers.ModelSerializer):
    staff_name = serializers.SerializerMethodField()
    employee_id = serializers.CharField(source="staff.employee_id", read_only=True)

    class Meta:
        model = PayrollAdjustment
        fields = ("id", "run", "staff", "staff_name", "employee_id", "kind", "name", "amount", "reason", "created_at")
        read_only_fields = fields

    def get_staff_name(self, adjustment):
        profile = adjustment.staff.profile
        return f"{profile.first_name} {profile.last_name}".strip()


class CreateRunSerializer(serializers.Serializer):
    year = serializers.IntegerField(min_value=2000, max_value=2200)
    month = serializers.IntegerField(min_value=1, max_value=12)
    notes = serializers.CharField(max_length=255, required=False, allow_blank=True, default="")


class CreateAdjustmentSerializer(serializers.Serializer):
    run = serializers.PrimaryKeyRelatedField(queryset=PayrollRun.objects.all())
    staff = serializers.PrimaryKeyRelatedField(queryset=StaffMember.objects.all())
    kind = serializers.ChoiceField(choices=SalaryComponent.Kind.choices)
    name = serializers.CharField(max_length=100)
    amount = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal("0.01"))
    reason = serializers.CharField(max_length=255)


class RecordPaymentSerializer(serializers.Serializer):
    paid_on = serializers.DateField()
    method = serializers.ChoiceField(choices=PayrollRun.Method.choices)
    reference = serializers.CharField(max_length=100, required=False, allow_blank=True, default="")


class ReasonSerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=255)
