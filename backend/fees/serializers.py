from decimal import Decimal

from rest_framework import serializers

from .models import (
    GATEWAY_CHOICES,
    FeeHead,
    FeeStructure,
    OnlinePaymentOrder,
    Payment,
    PaymentAllocation,
    StudentFee,
)
from .services import get_amount_paid, get_outstanding_balance


class FeeHeadSerializer(serializers.ModelSerializer):
    class Meta:
        model = FeeHead
        fields = ["id", "name", "description", "is_active", "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]


class FeeStructureSerializer(serializers.ModelSerializer):
    fee_head_name = serializers.CharField(source="fee_head.name", read_only=True)
    level_name = serializers.CharField(source="level.name", read_only=True, default=None)
    section_name = serializers.CharField(source="section.name", read_only=True, default=None)

    class Meta:
        model = FeeStructure
        fields = [
            "id", "fee_head", "fee_head_name", "academic_year", "level", "level_name",
            "section", "section_name", "amount", "frequency", "due_date",
            "effective_from", "effective_to", "is_active", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class StudentFeeSerializer(serializers.ModelSerializer):
    fee_head_name = serializers.CharField(source="fee_head.name", read_only=True)
    amount_paid = serializers.SerializerMethodField()
    outstanding_balance = serializers.SerializerMethodField()

    class Meta:
        model = StudentFee
        fields = [
            "id", "student", "fee_structure", "fee_head", "fee_head_name", "academic_year",
            "level_name", "section_name", "amount_due", "discount_amount", "discount_reason",
            "due_date", "status", "cancellation_reason", "cancelled_at",
            "amount_paid", "outstanding_balance", "created_at", "updated_at",
        ]
        read_only_fields = fields

    def get_amount_paid(self, obj):
        return get_amount_paid(obj)

    def get_outstanding_balance(self, obj):
        return get_outstanding_balance(obj)


class AssignStudentFeeSerializer(serializers.Serializer):
    fee_structure = serializers.UUIDField(required=False, allow_null=True)
    fee_head = serializers.UUIDField(required=False, allow_null=True)
    academic_year = serializers.CharField(max_length=20)
    amount_due = serializers.DecimalField(max_digits=10, decimal_places=2, required=False, allow_null=True)
    due_date = serializers.DateField(required=False, allow_null=True)
    discount_amount = serializers.DecimalField(
        max_digits=10, decimal_places=2, required=False, allow_null=True, default=Decimal("0")
    )
    discount_reason = serializers.CharField(required=False, allow_blank=True, default="")

    def validate(self, attrs):
        fee_structure_id = attrs.get("fee_structure")
        fee_head_id = attrs.get("fee_head")
        amount_due = attrs.get("amount_due")

        if not fee_structure_id and not (fee_head_id and amount_due is not None):
            raise serializers.ValidationError(
                "Provide either 'fee_structure', or both 'fee_head' and 'amount_due'."
            )

        fee_structure = None
        if fee_structure_id:
            try:
                fee_structure = FeeStructure.objects.select_related("fee_head").get(id=fee_structure_id)
            except FeeStructure.DoesNotExist:
                raise serializers.ValidationError({"fee_structure": "Fee structure not found."})
            attrs["fee_structure_obj"] = fee_structure
            attrs["fee_head_obj"] = fee_structure.fee_head
            if amount_due is None:
                attrs["amount_due"] = fee_structure.amount
            if not attrs.get("due_date"):
                attrs["due_date"] = fee_structure.due_date
        else:
            try:
                fee_head = FeeHead.objects.get(id=fee_head_id)
            except FeeHead.DoesNotExist:
                raise serializers.ValidationError({"fee_head": "Fee head not found."})
            attrs["fee_head_obj"] = fee_head

        discount_amount = attrs.get("discount_amount") or Decimal("0")
        if discount_amount < 0:
            raise serializers.ValidationError({"discount_amount": "Discount cannot be negative."})
        if discount_amount > attrs["amount_due"]:
            raise serializers.ValidationError({"discount_amount": "Discount cannot exceed the amount due."})

        return attrs


class UpdateStudentFeeSerializer(serializers.Serializer):
    amount_due = serializers.DecimalField(max_digits=10, decimal_places=2, required=False)
    due_date = serializers.DateField(required=False, allow_null=True)
    discount_amount = serializers.DecimalField(max_digits=10, decimal_places=2, required=False)
    discount_reason = serializers.CharField(required=False, allow_blank=True)


class CancelStudentFeeSerializer(serializers.Serializer):
    cancellation_reason = serializers.CharField(allow_blank=False, max_length=255)


class PaymentAllocationInputSerializer(serializers.Serializer):
    student_fee = serializers.UUIDField()
    amount = serializers.DecimalField(max_digits=10, decimal_places=2)


class RecordPaymentSerializer(serializers.Serializer):
    student = serializers.UUIDField()
    amount = serializers.DecimalField(max_digits=10, decimal_places=2)
    method = serializers.ChoiceField(choices=[c[0] for c in Payment._meta.get_field("method").choices])
    reference_note = serializers.CharField(required=False, allow_blank=True, default="")
    allocations = PaymentAllocationInputSerializer(many=True)

    def validate_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError("Payment amount must be positive.")
        return value


class ReversePaymentSerializer(serializers.Serializer):
    reason = serializers.CharField(required=False, allow_blank=True, default="")


class PaymentAllocationSerializer(serializers.ModelSerializer):
    fee_head_name = serializers.CharField(source="student_fee.fee_head.name", read_only=True)

    class Meta:
        model = PaymentAllocation
        fields = ["id", "student_fee", "fee_head_name", "amount", "created_at"]
        read_only_fields = fields


class PaymentSerializer(serializers.ModelSerializer):
    student_name = serializers.SerializerMethodField()
    allocations = PaymentAllocationSerializer(many=True, read_only=True)
    is_reversed = serializers.SerializerMethodField()

    class Meta:
        model = Payment
        fields = [
            "id", "student", "student_name", "amount", "method", "status", "receipt_number",
            "reference_note", "reverses", "recorded_by", "allocations", "is_reversed", "created_at",
        ]
        read_only_fields = fields

    def get_student_name(self, obj):
        profile = obj.student.profile
        return f"{profile.first_name} {profile.last_name}"

    def get_is_reversed(self, obj):
        return hasattr(obj, "reversal")


class OnlinePaymentOrderSerializer(serializers.ModelSerializer):
    student_name = serializers.SerializerMethodField()
    receipt_number = serializers.SerializerMethodField()

    class Meta:
        model = OnlinePaymentOrder
        fields = [
            "id",
            "student",
            "student_name",
            "amount",
            "gateway",
            "status",
            "allocations_snapshot",
            "gateway_order_id",
            "gateway_reference",
            "gateway_response",
            "reconciliation_reason",
            "created_by_user_id",
            "created_at",
            "updated_at",
            "expires_at",
            "completed_at",
            "payment",
            "receipt_number",
        ]
        read_only_fields = fields

    def get_student_name(self, obj):
        profile = getattr(obj.student, "profile", None)
        if profile:
            return f"{profile.first_name} {profile.last_name}"
        return ""

    def get_receipt_number(self, obj):
        return obj.payment.receipt_number if obj.payment else None


class PublicOnlinePaymentOrderSerializer(serializers.ModelSerializer):
    """
    What the UNAUTHENTICATED payment-return endpoints may reveal about an order: only what the
    return page needs to continue (poll the order, link the receipt). No student identity,
    creator, allocation snapshot, gateway payload or reconciliation diagnostics.
    """

    class Meta:
        model = OnlinePaymentOrder
        fields = ["id", "gateway_order_id", "status", "amount", "payment"]
        read_only_fields = fields


class OnlinePaymentOrderInitiateSerializer(serializers.Serializer):
    student = serializers.UUIDField(required=True)
    amount = serializers.DecimalField(max_digits=10, decimal_places=2, required=True)
    gateway = serializers.ChoiceField(choices=GATEWAY_CHOICES, default="esewa")
    allocations = PaymentAllocationInputSerializer(many=True, required=True)
    # Accepted for backwards compatibility and IGNORED: the gateway callback URLs are built
    # server-side from the tenant's primary domain (see fees.callbacks.build_callback_urls).
    return_url = serializers.CharField(required=False, allow_blank=True, default="")
    failure_url = serializers.CharField(required=False, allow_blank=True, default="")
    ttl_minutes = serializers.IntegerField(required=False, default=60, min_value=5, max_value=1440)

    def validate_amount(self, value):
        if value <= Decimal("0"):
            raise serializers.ValidationError("Payment amount must be positive.")
        return value

    def validate(self, attrs):
        amount = attrs.get("amount")
        allocations = attrs.get("allocations", [])
        if not allocations:
            raise serializers.ValidationError({"allocations": "At least one allocation is required."})

        total_allocated = sum((Decimal(str(a["amount"])) for a in allocations), Decimal("0"))
        if total_allocated != amount:
            raise serializers.ValidationError(
                {"allocations": "The sum of allocations must equal the payment amount."}
            )

        fee_ids = [a["student_fee"] for a in allocations]
        if len(set(fee_ids)) != len(fee_ids):
            raise serializers.ValidationError({"allocations": "Duplicate fee record in the same payment."})

        return attrs


class ParentPortalChildPayFeeSerializer(serializers.Serializer):
    amount = serializers.DecimalField(max_digits=10, decimal_places=2, required=True)
    gateway = serializers.ChoiceField(choices=GATEWAY_CHOICES, default="esewa")
    allocations = PaymentAllocationInputSerializer(many=True, required=True)
    # Accepted for backwards compatibility and IGNORED: the gateway callback URLs are built
    # server-side from the tenant's primary domain (see fees.callbacks.build_callback_urls).
    return_url = serializers.CharField(required=False, allow_blank=True, default="")
    failure_url = serializers.CharField(required=False, allow_blank=True, default="")
    ttl_minutes = serializers.IntegerField(required=False, default=60, min_value=5, max_value=1440)

    def validate_amount(self, value):
        if value <= Decimal("0"):
            raise serializers.ValidationError("Payment amount must be positive.")
        return value

    def validate(self, attrs):
        amount = attrs.get("amount")
        allocations = attrs.get("allocations", [])
        if not allocations:
            raise serializers.ValidationError({"allocations": "At least one allocation is required."})

        total_allocated = sum((Decimal(str(a["amount"])) for a in allocations), Decimal("0"))
        if total_allocated != amount:
            raise serializers.ValidationError(
                {"allocations": "The sum of allocations must equal the payment amount."}
            )

        fee_ids = [a["student_fee"] for a in allocations]
        if len(set(fee_ids)) != len(fee_ids):
            raise serializers.ValidationError({"allocations": "Duplicate fee record in the same payment."})

        return attrs


class OnlinePaymentVerifySerializer(serializers.Serializer):
    order_id = serializers.UUIDField(required=False, allow_null=True)
    data = serializers.CharField(required=False, allow_blank=True)
    encoded_data = serializers.CharField(required=False, allow_blank=True)
