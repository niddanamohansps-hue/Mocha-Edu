import uuid
from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q


class Vehicle(models.Model):
    """A school bus or van. Capacity is the number of student seats."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    registration_number = models.CharField(max_length=30, unique=True)
    name = models.CharField(max_length=100, blank=True)
    make_model = models.CharField(max_length=100, blank=True)
    capacity = models.PositiveSmallIntegerField(validators=[MinValueValidator(1)])
    insurance_expiry = models.DateField(null=True, blank=True)
    fitness_expiry = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    notes = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["registration_number"]

    def __str__(self):
        return self.registration_number


class Driver(models.Model):
    """A driver or helper. Kept as its own record: many are contractors who are not on the staff list,
    so the link to a staff member is optional."""

    class Role(models.TextChoices):
        DRIVER = "driver", "Driver"
        HELPER = "helper", "Helper"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    full_name = models.CharField(max_length=150)
    role = models.CharField(max_length=10, choices=Role.choices, default=Role.DRIVER)
    phone = models.CharField(max_length=30, blank=True)
    license_number = models.CharField(max_length=50, blank=True)
    license_expiry = models.DateField(null=True, blank=True)
    staff = models.ForeignKey("staff.StaffMember", null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    is_active = models.BooleanField(default=True)
    notes = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["full_name"]

    def __str__(self):
        return self.full_name


class Route(models.Model):
    """One bus run: a vehicle, its driver and helper, and an ordered list of stops."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, unique=True)
    vehicle = models.ForeignKey(Vehicle, null=True, blank=True, on_delete=models.PROTECT, related_name="routes")
    driver = models.ForeignKey(Driver, null=True, blank=True, on_delete=models.PROTECT, related_name="driven_routes")
    helper = models.ForeignKey(Driver, null=True, blank=True, on_delete=models.PROTECT, related_name="helped_routes")
    start_point = models.CharField(max_length=100, blank=True, help_text="Where the morning run begins, if not at a stop.")
    end_point = models.CharField(max_length=100, blank=True, help_text="Where the morning run ends, usually the school.")
    monthly_fee = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal("0"), validators=[MinValueValidator(Decimal("0"))],
        help_text="The default monthly fee for a student on this route. A stop with its own fee overrides it.",
    )
    is_active = models.BooleanField(default=True)
    notes = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.CheckConstraint(condition=Q(monthly_fee__gte=0), name="transport_route_fee_not_negative"),
        ]

    def __str__(self):
        return self.name


class RouteStop(models.Model):
    """A pick-up/drop-off point on a route. Stops are optional: a school that charges one fare per route
    needs none. A stop's own monthly fee, when set, overrides the route's fee (the fare depends on how far
    the student rides)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    route = models.ForeignKey(Route, on_delete=models.CASCADE, related_name="stops")
    name = models.CharField(max_length=100)
    sequence = models.PositiveSmallIntegerField(validators=[MinValueValidator(1)])
    pickup_time = models.TimeField(null=True, blank=True)
    drop_time = models.TimeField(null=True, blank=True)
    monthly_fee = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True, validators=[MinValueValidator(Decimal("0"))],
        help_text="Leave empty to use the route's fee.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["route", "sequence"]
        constraints = [
            models.UniqueConstraint(fields=["route", "sequence"], name="transport_stop_unique_sequence"),
            models.UniqueConstraint(fields=["route", "name"], name="transport_stop_unique_name"),
            models.CheckConstraint(
                condition=Q(monthly_fee__isnull=True) | Q(monthly_fee__gte=0), name="transport_stop_fee_not_negative"
            ),
        ]

    def __str__(self):
        return f"{self.route.name} - {self.name}"

    @property
    def fee(self):
        """The monthly fee that applies at this stop."""
        return self.route.monthly_fee if self.monthly_fee is None else self.monthly_fee


class StudentTransport(models.Model):
    """A student's seat on a route, at a stop when the route has stops, from when to when. History is kept:
    moving a student ends the old row and starts a new one, and the database allows at most one open row
    per student."""

    class Mode(models.TextChoices):
        BOTH = "both", "Both ways"
        PICKUP = "pickup", "Pick-up only"
        DROPOFF = "dropoff", "Drop-off only"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    student = models.ForeignKey("students.Student", on_delete=models.PROTECT, related_name="transport_assignments")
    route = models.ForeignKey(Route, on_delete=models.PROTECT, related_name="seats")
    stop = models.ForeignKey(RouteStop, null=True, blank=True, on_delete=models.PROTECT, related_name="assignments")
    mode = models.CharField(max_length=10, choices=Mode.choices, default=Mode.BOTH)
    pickup_note = models.CharField(max_length=255, blank=True, help_text="For a route without stops, e.g. 'near the temple'.")
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    created_by_user_id = models.UUIDField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-start_date", "-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["student"], condition=Q(end_date__isnull=True), name="transport_one_open_seat_per_student"
            ),
            models.CheckConstraint(
                condition=Q(end_date__isnull=True) | Q(end_date__gte=models.F("start_date")),
                name="transport_seat_end_after_start",
            ),
        ]

    def __str__(self):
        return f"{self.student} - {self.stop or self.route}"

    @property
    def fee(self):
        return self.stop.fee if self.stop_id else self.route.monthly_fee


class TransportBill(models.Model):
    """Records that a student was billed transport for a month, and links to the fee that was created.
    The unique (student, month) rule is what makes the monthly run safe to repeat."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    student = models.ForeignKey("students.Student", on_delete=models.PROTECT, related_name="transport_bills")
    month = models.DateField(help_text="The first day of the month that was billed.")
    route = models.ForeignKey(Route, on_delete=models.PROTECT, related_name="bills")
    stop = models.ForeignKey(RouteStop, null=True, blank=True, on_delete=models.PROTECT, related_name="bills")
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    student_fee = models.OneToOneField("fees.StudentFee", on_delete=models.PROTECT, related_name="transport_bill")
    billed_by_user_id = models.UUIDField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-month", "student"]
        constraints = [
            models.UniqueConstraint(fields=["student", "month"], name="transport_one_bill_per_student_month"),
        ]

    def __str__(self):
        return f"{self.student} - {self.month:%Y-%m}"
