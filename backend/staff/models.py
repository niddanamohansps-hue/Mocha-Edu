from django.db import models
import uuid


class StaffMember(models.Model):
    """
    Employment Domain: Stores professional and organizational data for staff.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    profile = models.OneToOneField(
        "profiles.Profile", on_delete=models.CASCADE, related_name="staff_record"
    )

    employee_id = models.CharField(max_length=50, unique=True)
    designation = models.CharField(max_length=100)
    department = models.CharField(max_length=100, blank=True)

    joining_date = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    # Qualification and background
    qualification = models.TextField(blank=True)
    experience_years = models.PositiveIntegerField(default=0)

    def __str__(self):
        return f"{self.profile.first_name} - {self.employee_id} ({self.designation})"


class Instructor(models.Model):
    """
    Extends StaffMember for teaching-specific data.
    """

    staff_member = models.OneToOneField(
        StaffMember, on_delete=models.CASCADE, related_name="instructor_record"
    )
    specialization = models.CharField(max_length=100)
    license_number = models.CharField(max_length=100, blank=True)
    bio = models.TextField(blank=True)

    def __str__(self):
        return f"Instructor: {self.staff_member.profile.first_name} ({self.specialization})"


# =============================================================================
# Staff Leave Management Domain Models (Phase 5)
# =============================================================================

from decimal import Decimal


class LeaveType(models.Model):
    """
    Tenant-configurable leave categories (e.g. Casual Leave, Sick Leave, Maternity Leave).
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100)
    code = models.CharField(
        max_length=20, unique=True, help_text="Short identifier e.g. 'CL', 'SL', 'ML'"
    )
    description = models.TextField(blank=True, default="")
    annual_allocation_days = models.DecimalField(
        max_digits=5, decimal_places=1, default=12.0, help_text="Default days granted per academic/leave year"
    )
    is_paid = models.BooleanField(default=True, help_text="Whether this leave type is fully paid")
    requires_document = models.BooleanField(
        default=False, help_text="Whether medical slip or proof document is mandatory"
    )
    max_consecutive_days = models.PositiveIntegerField(
        null=True, blank=True, help_text="Maximum days that can be taken consecutively without special approval"
    )
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.code})"


class StaffLeaveBalance(models.Model):
    """
    Leave quota accounting for each staff member, leave type, and academic/leave year.
    Enforces atomic reservation:
      available_days = allocated_days - (used_days + pending_days)
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    staff = models.ForeignKey(
        StaffMember, on_delete=models.CASCADE, related_name="leave_balances"
    )
    leave_type = models.ForeignKey(
        LeaveType, on_delete=models.CASCADE, related_name="staff_balances"
    )
    academic_year = models.CharField(max_length=20)
    academic_year_ref = models.ForeignKey(
        "academics.AcademicYear",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
    )
    allocated_days = models.DecimalField(max_digits=5, decimal_places=1, default=0.0)
    used_days = models.DecimalField(max_digits=5, decimal_places=1, default=0.0)
    pending_days = models.DecimalField(max_digits=5, decimal_places=1, default=0.0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["staff", "leave_type"]
        constraints = [
            models.UniqueConstraint(
                fields=["staff", "leave_type", "academic_year"],
                name="unique_staff_leave_balance_per_year",
            ),
            models.CheckConstraint(
                condition=models.Q(allocated_days__gte=0),
                name="leave_balance_allocated_nonnegative",
            ),
            models.CheckConstraint(
                condition=models.Q(used_days__gte=0),
                name="leave_balance_used_nonnegative",
            ),
            models.CheckConstraint(
                condition=models.Q(pending_days__gte=0),
                name="leave_balance_pending_nonnegative",
            ),
        ]

    @property
    def available_days(self):
        rem = self.allocated_days - (self.used_days + self.pending_days)
        return max(Decimal("0.0"), rem)

    def __str__(self):
        return f"{self.staff} - {self.leave_type.code} ({self.academic_year}): {self.available_days} available"


LEAVE_STATUS_CHOICES = [
    ("pending", "Pending Review"),
    ("approved", "Approved"),
    ("rejected", "Rejected"),
    ("cancelled", "Cancelled"),
]

HALF_DAY_SESSION_CHOICES = [
    ("", "Full Day"),
    ("morning", "Morning Session"),
    ("afternoon", "Afternoon Session"),
]


class LeaveApplication(models.Model):
    """
    A staff member's request for temporary absence over a date range.
    Duration (working_days) is computed strictly on the server excluding weekly off days and holidays.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    staff = models.ForeignKey(
        StaffMember, on_delete=models.CASCADE, related_name="leave_applications"
    )
    leave_type = models.ForeignKey(
        LeaveType, on_delete=models.PROTECT, related_name="applications"
    )
    academic_year = models.CharField(max_length=20)
    academic_year_ref = models.ForeignKey(
        "academics.AcademicYear",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
    )
    start_date = models.DateField()
    end_date = models.DateField()
    is_half_day = models.BooleanField(default=False)
    half_day_session = models.CharField(
        max_length=20, choices=HALF_DAY_SESSION_CHOICES, blank=True, default=""
    )
    working_days = models.DecimalField(max_digits=4, decimal_places=1, default=1.0)
    reason = models.TextField()
    document = models.FileField(upload_to="leave_documents/%Y/%m/", null=True, blank=True)
    document_name = models.CharField(max_length=255, blank=True, default="")
    status = models.CharField(
        max_length=20, choices=LEAVE_STATUS_CHOICES, default="pending", db_index=True
    )

    applied_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-applied_at"]
        indexes = [
            models.Index(fields=["staff", "status"]),
            models.Index(fields=["academic_year", "status"]),
            models.Index(fields=["start_date", "end_date"]),
        ]

    def __str__(self):
        return f"{self.staff} - {self.leave_type.code} ({self.start_date} to {self.end_date}) [{self.status}]"


class LeaveApproval(models.Model):
    """
    Immutable audit history of review decisions for a LeaveApplication.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    application = models.ForeignKey(
        LeaveApplication, on_delete=models.CASCADE, related_name="approvals"
    )
    approver = models.ForeignKey(
        StaffMember,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="decided_leave_applications",
    )
    decision = models.CharField(
        max_length=20,
        choices=[("approved", "Approved"), ("rejected", "Rejected"), ("cancelled", "Cancelled")],
    )
    comments = models.TextField(blank=True, default="")
    decided_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-decided_at"]

    def __str__(self):
        return f"{self.application.id} - {self.decision} by {self.approver} at {self.decided_at}"

