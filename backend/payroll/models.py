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
