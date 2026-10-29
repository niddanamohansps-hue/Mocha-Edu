from decimal import Decimal
from rest_framework import serializers

from .models import Expense, ExpenseCategory, PaymentAccount, CashbookEntry
from .services import generate_voucher_number, generate_entry_number


class ExpenseCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = ExpenseCategory
        fields = [
            "id",
            "name",
            "code",
            "description",
            "is_active",
            "sort_order",
            "created_at",
            "updated_at",
        ]


class PaymentAccountSerializer(serializers.ModelSerializer):
    class Meta:
        model = PaymentAccount
        fields = [
            "id",
            "name",
            "account_type",
            "bank_name",
            "account_number",
            "ifsc_code",
            "opening_balance",
            "is_default",
            "is_active",
            "created_at",
            "updated_at",
        ]

    def validate_opening_balance(self, value):
        if value < Decimal("0.00"):
            raise serializers.ValidationError("Opening balance cannot be negative.")
        return value


class ExpenseSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source="category.name", read_only=True)
    category_code = serializers.CharField(source="category.code", read_only=True)
    payment_account_name = serializers.CharField(source="payment_account.name", read_only=True)

    class Meta:
        model = Expense
        fields = [
            "id",
            "voucher_number",
            "category",
            "category_name",
            "category_code",
            "payment_account",
            "payment_account_name",
            "amount",
            "expense_date",
            "payment_method",
            "paid_to",
            "reference_number",
            "description",
            "receipt_file",
            "status",
            "cancelled_at",
            "cancellation_reason",
            "created_by_user_id",
            "approved_by_user_id",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "voucher_number",
            "cancelled_at",
            "created_by_user_id",
            "approved_by_user_id",
            "created_at",
            "updated_at",
        ]

    def validate_amount(self, value):
        if value <= Decimal("0.00"):
            raise serializers.ValidationError("Expense amount must be greater than zero.")
        return value

    def create(self, validated_data):
        if "voucher_number" not in validated_data or not validated_data["voucher_number"]:
            target_date = validated_data.get("expense_date")
            validated_data["voucher_number"] = generate_voucher_number(target_date)

        request = self.context.get("request")
        if request and request.user and request.user.is_authenticated:
            validated_data["created_by_user_id"] = request.user.id
            if validated_data.get("status") == Expense.Status.APPROVED:
                validated_data["approved_by_user_id"] = request.user.id

        # If payment_account not provided, default to the default account
        if not validated_data.get("payment_account"):
            def_acc = PaymentAccount.objects.filter(is_default=True).first()
            if def_acc:
                validated_data["payment_account"] = def_acc

        return super().create(validated_data)


class ExpenseCancelSerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=255, required=True)


class CashbookEntrySerializer(serializers.ModelSerializer):
    from_account_name = serializers.CharField(source="from_account.name", read_only=True)
    to_account_name = serializers.CharField(source="to_account.name", read_only=True)

    class Meta:
        model = CashbookEntry
        fields = [
            "id",
            "entry_number",
            "entry_type",
            "amount",
            "entry_date",
            "from_account",
            "from_account_name",
            "to_account",
            "to_account_name",
            "source_or_payee",
            "payment_method",
            "reference_number",
            "description",
            "created_by_user_id",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "entry_number",
            "created_by_user_id",
            "created_at",
        ]

    def validate_amount(self, value):
        if value <= Decimal("0.00"):
            raise serializers.ValidationError("Amount must be greater than zero.")
        return value

    def validate(self, attrs):
        entry_type = attrs.get("entry_type")
        from_acc = attrs.get("from_account")
        to_acc = attrs.get("to_account")

        if entry_type == CashbookEntry.EntryType.TRANSFER:
            if not from_acc:
                raise serializers.ValidationError({"from_account": "Source account is required for transfers."})
            if not to_acc:
                raise serializers.ValidationError({"to_account": "Destination account is required for transfers."})
            if from_acc == to_acc:
                raise serializers.ValidationError({"to_account": "Source and destination accounts must be different."})
        elif entry_type == CashbookEntry.EntryType.INCOME:
            if not to_acc:
                raise serializers.ValidationError({"to_account": "Receiving account is required for direct income."})

        return attrs

    def create(self, validated_data):
        entry_type = validated_data.get("entry_type")
        target_date = validated_data.get("entry_date")
        validated_data["entry_number"] = generate_entry_number(entry_type, target_date)

        request = self.context.get("request")
        if request and request.user and request.user.is_authenticated:
            validated_data["created_by_user_id"] = request.user.id

        return super().create(validated_data)

