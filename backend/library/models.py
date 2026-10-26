import uuid
from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models, transaction
from django.db.models import Q


class BookCategory(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "book categories"

    def __str__(self):
        return self.name


class Book(models.Model):
    """A title. The physical books are ``BookCopy`` rows, so a school with three copies of one title
    has one Book and three copies, each lent out and returned on its own."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=255)
    author = models.CharField(max_length=255, blank=True)
    isbn = models.CharField(max_length=20, blank=True)
    category = models.ForeignKey(BookCategory, null=True, blank=True, on_delete=models.PROTECT, related_name="books")
    publisher = models.CharField(max_length=150, blank=True)
    publication_year = models.PositiveSmallIntegerField(null=True, blank=True)
    shelf_location = models.CharField(max_length=100, blank=True)
    price = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True, validators=[MinValueValidator(Decimal("0"))],
        help_text="What a lost copy costs the borrower. Empty means no charge for a lost copy.",
    )
    description = models.CharField(max_length=500, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["title", "author"]
        indexes = [models.Index(fields=["isbn"], name="library_book_isbn_idx")]
        constraints = [
            models.CheckConstraint(condition=Q(price__isnull=True) | Q(price__gte=0), name="library_book_price_not_negative"),
        ]

    def __str__(self):
        return self.title


class BookCopy(models.Model):
    class Status(models.TextChoices):
        AVAILABLE = "available", "Available"
        ISSUED = "issued", "Issued"
        LOST = "lost", "Lost"
        WITHDRAWN = "withdrawn", "Withdrawn"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    book = models.ForeignKey(Book, on_delete=models.PROTECT, related_name="copies")
    accession_number = models.CharField(max_length=40, unique=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.AVAILABLE)
    notes = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["book__title", "accession_number"]
        verbose_name_plural = "book copies"

    def __str__(self):
        return f"{self.book.title} ({self.accession_number})"


class LibrarySettings(models.Model):
    """The school's library rules: exactly one row per school (a unique ``singleton``). Reading never
    writes: with no row, ``load()`` returns the defaults. A fine of 0 a day means the library charges none."""

    EDITABLE_FIELDS = (
        "student_loan_days", "staff_loan_days", "student_max_books", "staff_max_books", "max_renewals", "fine_per_day",
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    singleton = models.BooleanField(default=True, unique=True, editable=False)
    student_loan_days = models.PositiveSmallIntegerField(default=14, validators=[MinValueValidator(1)])
    staff_loan_days = models.PositiveSmallIntegerField(default=30, validators=[MinValueValidator(1)])
    student_max_books = models.PositiveSmallIntegerField(default=3, validators=[MinValueValidator(1)])
    staff_max_books = models.PositiveSmallIntegerField(default=5, validators=[MinValueValidator(1)])
    max_renewals = models.PositiveSmallIntegerField(default=1)
    fine_per_day = models.DecimalField(
        max_digits=8, decimal_places=2, default=Decimal("0"), validators=[MinValueValidator(Decimal("0"))]
    )
    updated_by_user_id = models.UUIDField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "library settings"
        constraints = [
            models.CheckConstraint(condition=Q(singleton=True), name="library_settings_singleton_true"),
            models.CheckConstraint(condition=Q(fine_per_day__gte=0), name="library_settings_fine_not_negative"),
        ]

    def __str__(self):
        return "Library settings"

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


class Loan(models.Model):
    """One copy lent to one student or one staff member. At most one open loan per copy is enforced by the
    database, so two librarians cannot lend the same book at once."""

    class Outcome(models.TextChoices):
        RETURNED = "returned", "Returned"
        LOST = "lost", "Lost"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    copy = models.ForeignKey(BookCopy, on_delete=models.PROTECT, related_name="loans")
    student = models.ForeignKey("students.Student", null=True, blank=True, on_delete=models.PROTECT, related_name="library_loans")
    staff = models.ForeignKey("staff.StaffMember", null=True, blank=True, on_delete=models.PROTECT, related_name="library_loans")
    issued_on = models.DateField()
    due_on = models.DateField()
    returned_on = models.DateField(null=True, blank=True)
    outcome = models.CharField(max_length=10, choices=Outcome.choices, blank=True)
    renewals = models.PositiveSmallIntegerField(default=0)
    issued_by_user_id = models.UUIDField(null=True, blank=True)
    closed_by_user_id = models.UUIDField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-issued_on", "-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["copy"], condition=Q(returned_on__isnull=True), name="library_one_open_loan_per_copy"),
            models.CheckConstraint(
                condition=(Q(student__isnull=False) & Q(staff__isnull=True)) | (Q(student__isnull=True) & Q(staff__isnull=False)),
                name="library_loan_exactly_one_borrower",
            ),
            models.CheckConstraint(condition=Q(due_on__gte=models.F("issued_on")), name="library_loan_due_after_issue"),
            models.CheckConstraint(
                condition=Q(returned_on__isnull=True) | Q(returned_on__gte=models.F("issued_on")),
                name="library_loan_return_after_issue",
            ),
        ]
        indexes = [models.Index(fields=["due_on"], name="library_loan_due_idx")]

    def __str__(self):
        return f"{self.copy} -> {self.student or self.staff}"

    @property
    def is_open(self):
        return self.returned_on is None


class Fine(models.Model):
    """A charge raised when a book comes back late or is lost. A student's fine is billed into Fees (one
    ``StudentFee`` under the Library head) so it is paid and receipted there; a staff member's is collected
    at the library. Either can be waived with a reason."""

    class Kind(models.TextChoices):
        OVERDUE = "overdue", "Overdue"
        LOST = "lost", "Lost book"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        BILLED = "billed", "Billed in Fees"
        COLLECTED = "collected", "Collected"
        WAIVED = "waived", "Waived"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    loan = models.ForeignKey(Loan, on_delete=models.PROTECT, related_name="fines")
    kind = models.CharField(max_length=10, choices=Kind.choices)
    amount = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))])
    days_overdue = models.PositiveIntegerField(default=0)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    student_fee = models.OneToOneField("fees.StudentFee", null=True, blank=True, on_delete=models.PROTECT, related_name="library_fine")
    waive_reason = models.CharField(max_length=255, blank=True)
    resolved_by_user_id = models.UUIDField(null=True, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["loan", "kind"], name="library_one_fine_per_loan_and_kind"),
            models.CheckConstraint(condition=Q(amount__gt=0), name="library_fine_amount_positive"),
        ]

    def __str__(self):
        return f"{self.get_kind_display()} fine {self.amount}"
