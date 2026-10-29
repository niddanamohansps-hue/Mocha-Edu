import uuid
from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q
from django.utils import timezone

MONEY = {"max_digits": 12, "decimal_places": 2}


class ExpenseCategory(models.Model):
    """
    Cost center/category for school operational expenses (e.g. Transport & Fuel,
    Electricity & Utilities, Repairs & Maintenance, Academic Supplies).
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, unique=True)
    code = models.CharField(max_length=30, unique=True)
    description = models.CharField(max_length=255, blank=True)
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["sort_order", "name"]
        verbose_name_plural = "expense categories"

    def __str__(self):
        return f"{self.name} ({self.code})"


class PaymentAccount(models.Model):
    """
    Physical or bank account where the school holds funds:
    - Main Cash in Hand (cash counter drawer at front office)
    - Bank Account (SBI, HDFC, ICICI, etc. for cheques, RTGS/NEFT, UPI)
    - Principal / Petty Cash Imprest Account
    """

    class AccountType(models.TextChoices):
        CASH = "cash", "Cash in Hand"
        BANK = "bank", "Bank Account"
        OTHER = "other", "Other"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, unique=True)
    account_type = models.CharField(max_length=20, choices=AccountType.choices, default=AccountType.CASH)
    bank_name = models.CharField(max_length=100, blank=True)
    account_number = models.CharField(max_length=50, blank=True)
    ifsc_code = models.CharField(max_length=20, blank=True)
    opening_balance = models.DecimalField(default=Decimal("0.00"), **MONEY)
    is_default = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-is_default", "name"]

    def __str__(self):
        if self.account_type == self.AccountType.BANK and self.bank_name:
            return f"{self.name} - {self.bank_name} ({self.account_number[-4:] if len(self.account_number) >= 4 else self.account_number})"
        return self.name

    def save(self, *args, **kwargs):
        if self.is_default:
            # Enforce at most one default account
            PaymentAccount.objects.filter(is_default=True).exclude(pk=self.pk).update(is_default=False)
        super().save(*args, **kwargs)


class Expense(models.Model):
    """
    An expense voucher recorded by the school.
    Vouchers can be recorded directly in 'approved' status or saved as 'draft'
    for approval by the Principal or School Owner.
    """

    class PaymentMethod(models.TextChoices):
        CASH = "cash", "Cash"
        CHEQUE = "cheque", "Cheque"
        BANK_TRANSFER = "bank_transfer", "Bank Transfer / NEFT / RTGS"
        UPI = "upi", "UPI / QR"
        OTHER = "other", "Other"

    class Status(models.TextChoices):
        APPROVED = "approved", "Approved"
        DRAFT = "draft", "Draft"
        CANCELLED = "cancelled", "Cancelled"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    voucher_number = models.CharField(max_length=50, unique=True)
    category = models.ForeignKey(ExpenseCategory, on_delete=models.PROTECT, related_name="expenses")
    payment_account = models.ForeignKey(
        PaymentAccount,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="expenses",
    )
    amount = models.DecimalField(validators=[MinValueValidator(Decimal("0.01"))], **MONEY)
    expense_date = models.DateField(default=timezone.localdate)
    payment_method = models.CharField(max_length=20, choices=PaymentMethod.choices, default=PaymentMethod.CASH)
    paid_to = models.CharField(max_length=200, help_text="Vendor, shop, contractor, or staff beneficiary")
    reference_number = models.CharField(
        max_length=100,
        blank=True,
        help_text="Bill no., invoice no., cheque no., or UPI transaction reference",
    )
    description = models.TextField(blank=True, help_text="Purpose or breakdown of expense items")
    receipt_file = models.FileField(upload_to="expense_receipts/", null=True, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.APPROVED)

    cancelled_at = models.DateTimeField(null=True, blank=True)
    cancellation_reason = models.CharField(max_length=255, blank=True)

    created_by_user_id = models.UUIDField(null=True, blank=True)
    approved_by_user_id = models.UUIDField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-expense_date", "-created_at"]
        indexes = [
            models.Index(fields=["expense_date", "status"], name="expense_date_status_idx"),
            models.Index(fields=["payment_account", "expense_date"], name="expense_account_date_idx"),
            models.Index(fields=["category", "expense_date"], name="expense_cat_date_idx"),
        ]
        constraints = [
            models.CheckConstraint(condition=Q(amount__gt=0), name="expense_amount_positive"),
        ]

    def __str__(self):
        return f"{self.voucher_number} - {self.paid_to} - ₹{self.amount} ({self.status})"


class CashbookEntry(models.Model):
    """
    Direct cash/bank movements that are NOT student fees or operational expenses:
    - Direct Miscellaneous Income: Prospectus/form sale, uniform sale, scrap sale, donations.
    - Contra Transfers: Cash deposited to Bank, or Cash withdrawn from Bank for petty cash.
    """

    class EntryType(models.TextChoices):
        INCOME = "income", "Direct Income"
        TRANSFER = "transfer", "Account Transfer / Contra"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    entry_number = models.CharField(max_length=50, unique=True)
    entry_type = models.CharField(max_length=20, choices=EntryType.choices)
    amount = models.DecimalField(validators=[MinValueValidator(Decimal("0.01"))], **MONEY)
    entry_date = models.DateField(default=timezone.localdate)

    # For transfers: from_account is debited/credited, to_account is the recipient
    from_account = models.ForeignKey(
        PaymentAccount,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="transfers_out",
    )
    # For direct income or transfers: to_account receives the funds
    to_account = models.ForeignKey(
        PaymentAccount,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="transfers_in",
    )

    source_or_payee = models.CharField(
        max_length=200,
        help_text="Source of income (e.g. Prospectus Sale) or Payee/Bearer for transfer",
    )
    payment_method = models.CharField(
        max_length=20,
        choices=Expense.PaymentMethod.choices,
        default=Expense.PaymentMethod.CASH,
    )
    reference_number = models.CharField(max_length=100, blank=True)
    description = models.TextField(blank=True)

    created_by_user_id = models.UUIDField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-entry_date", "-created_at"]
        indexes = [
            models.Index(fields=["entry_date", "entry_type"], name="cashbook_date_type_idx"),
            models.Index(fields=["to_account", "entry_date"], name="cashbook_to_acc_date_idx"),
            models.Index(fields=["from_account", "entry_date"], name="cashbook_from_acc_date_idx"),
        ]
        constraints = [
            models.CheckConstraint(condition=Q(amount__gt=0), name="cashbook_amount_positive"),
        ]

    def __str__(self):
        return f"{self.entry_number} - {self.entry_type} - ₹{self.amount}"

