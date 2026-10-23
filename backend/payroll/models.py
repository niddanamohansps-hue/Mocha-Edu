import uuid
from decimal import Decimal

from django.db import models, transaction
from django.db.models import Q

MONEY = {"max_digits": 12, "decimal_places": 2}


class SalaryComponent(models.Model):
    """A named part of pay: an earning (allowance, bonus) or a deduction (provident fund, tax...).

    The amount is either a fixed sum or a percentage of the basic salary. The school's accountant
    decides what exists and how much; nothing here knows any tax or fund rule.
    """

    class Kind(models.TextChoices):
        EARNING = "earning", "Earning"
        DEDUCTION = "deduction", "Deduction"

    class Calculation(models.TextChoices):
        FIXED = "fixed", "Fixed amount"
        PERCENT_OF_BASIC = "percent_of_basic", "Percentage of basic salary"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, unique=True)
    code = models.CharField(max_length=30, unique=True)
    kind = models.CharField(max_length=10, choices=Kind.choices)
    calculation = models.CharField(max_length=20, choices=Calculation.choices, default=Calculation.FIXED)
    # An amount when fixed (up to 2 decimals), a percentage when percent_of_basic (up to 3 decimals).
    default_value = models.DecimalField(max_digits=12, decimal_places=3, default=Decimal("0"))
    description = models.CharField(max_length=255, blank=True)
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["kind", "sort_order", "name"]
        constraints = [
            models.CheckConstraint(condition=Q(default_value__gte=0), name="payroll_component_value_nonneg"),
            models.CheckConstraint(
                condition=~Q(calculation="percent_of_basic") | Q(default_value__lte=100),
                name="payroll_component_percent_max",
            ),
        ]

    def __str__(self):
        return f"{self.name} ({self.kind})"


class StaffSalary(models.Model):
    """A staff member's basic monthly salary from a date. A raise is a NEW row, never an edit, so
    pay history is never rewritten."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    staff = models.ForeignKey("staff.StaffMember", on_delete=models.PROTECT, related_name="salaries")
    basic_amount = models.DecimalField(**MONEY)
    effective_from = models.DateField()
    note = models.CharField(max_length=255, blank=True)
    # Soft link to accounts.User (public schema), same convention as the other apps.
    created_by_user_id = models.UUIDField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-effective_from", "-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["staff", "effective_from"], name="payroll_salary_one_per_date"),
            models.CheckConstraint(condition=Q(basic_amount__gt=0), name="payroll_salary_positive"),
        ]

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise RuntimeError("A salary record is immutable; set a new salary instead.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise RuntimeError("A salary record can never be deleted; set a new salary instead.")

    def __str__(self):
        return f"{self.staff_id}: {self.basic_amount} from {self.effective_from}"


class StaffSalaryComponent(models.Model):
    """A component given to one staff member for a period. ``value`` overrides the component's
    default for this person. Ending it sets ``effective_to`` (the record stays); a staff member has
    at most one open assignment per component."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    staff = models.ForeignKey("staff.StaffMember", on_delete=models.PROTECT, related_name="salary_components")
    component = models.ForeignKey(SalaryComponent, on_delete=models.PROTECT, related_name="assignments")
    value = models.DecimalField(max_digits=12, decimal_places=3, null=True, blank=True)
    effective_from = models.DateField()
    effective_to = models.DateField(null=True, blank=True)
    created_by_user_id = models.UUIDField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["component__kind", "component__sort_order", "-effective_from"]
        constraints = [
            models.UniqueConstraint(
                fields=["staff", "component"], condition=Q(effective_to__isnull=True), name="payroll_staffcomp_one_open"
            ),
            models.CheckConstraint(
                condition=Q(effective_to__isnull=True) | Q(effective_to__gte=models.F("effective_from")),
                name="payroll_staffcomp_dates_ordered",
            ),
            models.CheckConstraint(
                condition=Q(value__isnull=True) | Q(value__gte=0), name="payroll_staffcomp_value_nonneg"
            ),
        ]

    def __str__(self):
        return f"{self.staff_id} / {self.component_id}"


class PayrollSettings(models.Model):
    """The school's payroll rules: exactly one row per school (a unique ``singleton``). Reading never
    writes: with no row, ``load()`` returns the defaults."""

    EDITABLE_FIELDS = ("round_to_whole_rupee", "require_separate_approver")

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    singleton = models.BooleanField(default=True, unique=True, editable=False)
    # Round each pay line to a whole rupee (half rounds up) instead of keeping paisa.
    round_to_whole_rupee = models.BooleanField(default=True)
    # The person who prepares a payroll run cannot be the one who approves it.
    require_separate_approver = models.BooleanField(default=True)
    updated_by_user_id = models.UUIDField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.CheckConstraint(condition=Q(singleton=True), name="payroll_settings_singleton_true")]

    def __str__(self):
        return "Payroll settings"

    @classmethod
    def load(cls):
        return cls.objects.filter(singleton=True).first() or cls()

    def editable_values(self):
        return {name: getattr(self, name) for name in self.EDITABLE_FIELDS}

    @classmethod
    def update_singleton(cls, *, user_id=None, **values):
        unknown = set(values) - set(cls.EDITABLE_FIELDS)
        if unknown:
            raise ValueError(f"Not editable: {sorted(unknown)}")
        with transaction.atomic():
            cls.objects.get_or_create(singleton=True)
            instance = cls.objects.select_for_update().get(singleton=True)
            previous = instance.editable_values()
            for name, value in values.items():
                setattr(instance, name, value)
            instance.updated_by_user_id = user_id
            instance.save()
        return instance, previous


class PayrollRun(models.Model):
    """One month's payroll for the whole school: draft -> calculated -> approved -> paid (or cancelled).

    Once approved the run and its payslips are locked: a mistake is corrected by cancelling the run
    (before it is paid) or by an adjustment in the next month's run, never by editing a closed one.
    """

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        CALCULATED = "calculated", "Calculated"
        APPROVED = "approved", "Approved"
        PAID = "paid", "Paid"
        CANCELLED = "cancelled", "Cancelled"

    class Method(models.TextChoices):
        BANK_TRANSFER = "bank_transfer", "Bank transfer"
        CASH = "cash", "Cash"
        CHEQUE = "cheque", "Cheque"
        OTHER = "other", "Other"

    LOCKED = ("approved", "paid")

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    year = models.PositiveSmallIntegerField()
    month = models.PositiveSmallIntegerField()
    period_start = models.DateField()
    period_end = models.DateField()
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.DRAFT)
    notes = models.CharField(max_length=255, blank=True)
    # What the calculation used, kept so the run can always be explained afterwards.
    working_days = models.PositiveSmallIntegerField(null=True, blank=True)
    weekly_off_days = models.JSONField(default=list, blank=True)
    round_to_whole_rupee = models.BooleanField(default=True)
    calculation_notes = models.JSONField(default=dict, blank=True)

    created_by_user_id = models.UUIDField(null=True, blank=True)
    # Whoever created the run or last calculated it: the one who may not also approve it.
    prepared_by_user_id = models.UUIDField(null=True, blank=True)
    calculated_at = models.DateTimeField(null=True, blank=True)
    approved_by_user_id = models.UUIDField(null=True, blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    paid_on = models.DateField(null=True, blank=True)
    paid_by_user_id = models.UUIDField(null=True, blank=True)
    payment_method = models.CharField(max_length=20, choices=Method.choices, blank=True)
    payment_reference = models.CharField(max_length=100, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    cancelled_by_user_id = models.UUIDField(null=True, blank=True)
    cancellation_reason = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-year", "-month", "-created_at"]
        constraints = [
            models.CheckConstraint(condition=Q(month__gte=1, month__lte=12), name="payroll_run_month_range"),
            models.UniqueConstraint(
                fields=["year", "month"], condition=~Q(status="cancelled"), name="payroll_run_one_per_month"
            ),
        ]

    def __str__(self):
        return f"Payroll {self.year}-{self.month:02d} ({self.status})"

    @property
    def is_locked(self):
        return self.status in self.LOCKED


class Payslip(models.Model):
    """One staff member's pay for one run. The name, designation and every amount are copied in, so a
    payslip never changes when the staff record or the salary structure changes later."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    run = models.ForeignKey(PayrollRun, on_delete=models.PROTECT, related_name="payslips")
    staff = models.ForeignKey("staff.StaffMember", on_delete=models.PROTECT, related_name="payslips")
    employee_id = models.CharField(max_length=50)
    staff_name = models.CharField(max_length=200)
    designation = models.CharField(max_length=100, blank=True)
    department = models.CharField(max_length=100, blank=True)
    basic_amount = models.DecimalField(**MONEY)
    gross_amount = models.DecimalField(**MONEY)
    deductions_amount = models.DecimalField(**MONEY)
    net_amount = models.DecimalField(max_digits=12, decimal_places=2)  # can be negative: flagged, never hidden
    working_days = models.PositiveSmallIntegerField()
    unpaid_days = models.DecimalField(max_digits=5, decimal_places=1, default=Decimal("0"))
    # Working days with no attendance record (paid, but worth a look before approving).
    unmarked_days = models.DecimalField(max_digits=5, decimal_places=1, default=Decimal("0"))
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["staff_name", "employee_id"]
        constraints = [models.UniqueConstraint(fields=["run", "staff"], name="payroll_payslip_one_per_run")]

    def _check_unlocked(self):
        if self.run.is_locked:
            raise RuntimeError("This payslip belongs to an approved payroll run and cannot be changed.")

    def save(self, *args, **kwargs):
        if not self._state.adding:
            self._check_unlocked()
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        self._check_unlocked()
        return super().delete(*args, **kwargs)

    @property
    def net_is_negative(self):
        return self.net_amount < 0

    def __str__(self):
        return f"{self.employee_id} {self.run_id}"


class PayslipLine(models.Model):
    """One line of a payslip, copied from the structure, the unpaid-days rule or an adjustment."""

    class Kind(models.TextChoices):
        BASIC = "basic", "Basic salary"
        EARNING = "earning", "Earning"
        DEDUCTION = "deduction", "Deduction"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    payslip = models.ForeignKey(Payslip, on_delete=models.CASCADE, related_name="lines")
    code = models.CharField(max_length=30)
    name = models.CharField(max_length=100)
    kind = models.CharField(max_length=10, choices=Kind.choices)
    amount = models.DecimalField(**MONEY)
    detail = models.CharField(max_length=255, blank=True)
    sort_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "id"]
        constraints = [models.CheckConstraint(condition=Q(amount__gte=0), name="payroll_line_amount_nonneg")]

    def save(self, *args, **kwargs):
        if not self._state.adding and self.payslip.run.is_locked:
            raise RuntimeError("This payslip line belongs to an approved payroll run and cannot be changed.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if self.payslip.run.is_locked:
            raise RuntimeError("This payslip line belongs to an approved payroll run and cannot be removed.")
        return super().delete(*args, **kwargs)


class PayrollAdjustment(models.Model):
    """A one-off addition or deduction for one person in one run (a bonus, an advance recovered, a
    correction from an earlier month). It has to say why. Only while the run is not yet approved."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    run = models.ForeignKey(PayrollRun, on_delete=models.PROTECT, related_name="adjustments")
    staff = models.ForeignKey("staff.StaffMember", on_delete=models.PROTECT, related_name="payroll_adjustments")
    kind = models.CharField(max_length=10, choices=SalaryComponent.Kind.choices)
    name = models.CharField(max_length=100)
    amount = models.DecimalField(**MONEY)
    reason = models.CharField(max_length=255)
    created_by_user_id = models.UUIDField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "id"]
        constraints = [models.CheckConstraint(condition=Q(amount__gt=0), name="payroll_adjustment_positive")]

    def delete(self, *args, **kwargs):
        if self.run.is_locked:
            raise RuntimeError("An adjustment of an approved payroll run cannot be removed.")
        return super().delete(*args, **kwargs)
