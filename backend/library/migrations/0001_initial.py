import uuid
from decimal import Decimal

import django.core.validators
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("fees", "0003_tenantpaymentgatewayconfig_onlinepaymentorder"),
        ("staff", "0002_leavetype_leaveapplication_leaveapproval_and_more"),
        ("students", "0007_admissiondocument_scan_details_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="BookCategory",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("name", models.CharField(max_length=100, unique=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={"verbose_name_plural": "book categories", "ordering": ["name"]},
        ),
        migrations.CreateModel(
            name="Book",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("title", models.CharField(max_length=255)),
                ("author", models.CharField(blank=True, max_length=255)),
                ("isbn", models.CharField(blank=True, max_length=20)),
                ("publisher", models.CharField(blank=True, max_length=150)),
                ("publication_year", models.PositiveSmallIntegerField(blank=True, null=True)),
                ("shelf_location", models.CharField(blank=True, max_length=100)),
                (
                    "price",
                    models.DecimalField(
                        blank=True,
                        decimal_places=2,
                        help_text="What a lost copy costs the borrower. Empty means no charge for a lost copy.",
                        max_digits=10,
                        null=True,
                        validators=[django.core.validators.MinValueValidator(Decimal("0"))],
                    ),
                ),
                ("description", models.CharField(blank=True, max_length=500)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "category",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="books",
                        to="library.bookcategory",
                    ),
                ),
            ],
            options={"ordering": ["title", "author"]},
        ),
        migrations.CreateModel(
            name="BookCopy",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("accession_number", models.CharField(max_length=40, unique=True)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("available", "Available"),
                            ("issued", "Issued"),
                            ("lost", "Lost"),
                            ("withdrawn", "Withdrawn"),
                        ],
                        default="available",
                        max_length=10,
                    ),
                ),
                ("notes", models.CharField(blank=True, max_length=255)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "book",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT, related_name="copies", to="library.book"
                    ),
                ),
            ],
            options={"verbose_name_plural": "book copies", "ordering": ["book__title", "accession_number"]},
        ),
        migrations.CreateModel(
            name="LibrarySettings",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("singleton", models.BooleanField(default=True, editable=False, unique=True)),
                (
                    "student_loan_days",
                    models.PositiveSmallIntegerField(
                        default=14, validators=[django.core.validators.MinValueValidator(1)]
                    ),
                ),
                (
                    "staff_loan_days",
                    models.PositiveSmallIntegerField(
                        default=30, validators=[django.core.validators.MinValueValidator(1)]
                    ),
                ),
                (
                    "student_max_books",
                    models.PositiveSmallIntegerField(
                        default=3, validators=[django.core.validators.MinValueValidator(1)]
                    ),
                ),
                (
                    "staff_max_books",
                    models.PositiveSmallIntegerField(
                        default=5, validators=[django.core.validators.MinValueValidator(1)]
                    ),
                ),
                ("max_renewals", models.PositiveSmallIntegerField(default=1)),
                (
                    "fine_per_day",
                    models.DecimalField(
                        decimal_places=2,
                        default=Decimal("0"),
                        max_digits=8,
                        validators=[django.core.validators.MinValueValidator(Decimal("0"))],
                    ),
                ),
                ("updated_by_user_id", models.UUIDField(blank=True, null=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"verbose_name_plural": "library settings"},
        ),
        migrations.CreateModel(
            name="Loan",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("issued_on", models.DateField()),
                ("due_on", models.DateField()),
                ("returned_on", models.DateField(blank=True, null=True)),
                (
                    "outcome",
                    models.CharField(
                        blank=True, choices=[("returned", "Returned"), ("lost", "Lost")], max_length=10
                    ),
                ),
                ("renewals", models.PositiveSmallIntegerField(default=0)),
                ("issued_by_user_id", models.UUIDField(blank=True, null=True)),
                ("closed_by_user_id", models.UUIDField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "copy",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT, related_name="loans", to="library.bookcopy"
                    ),
                ),
                (
                    "staff",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="library_loans",
                        to="staff.staffmember",
                    ),
                ),
                (
                    "student",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="library_loans",
                        to="students.student",
                    ),
                ),
            ],
            options={"ordering": ["-issued_on", "-created_at"]},
        ),
        migrations.CreateModel(
            name="Fine",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                (
                    "kind",
                    models.CharField(choices=[("overdue", "Overdue"), ("lost", "Lost book")], max_length=10),
                ),
                (
                    "amount",
                    models.DecimalField(
                        decimal_places=2,
                        max_digits=10,
                        validators=[django.core.validators.MinValueValidator(Decimal("0.01"))],
                    ),
                ),
                ("days_overdue", models.PositiveIntegerField(default=0)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("pending", "Pending"),
                            ("billed", "Billed in Fees"),
                            ("collected", "Collected"),
                            ("waived", "Waived"),
                        ],
                        default="pending",
                        max_length=10,
                    ),
                ),
                ("waive_reason", models.CharField(blank=True, max_length=255)),
                ("resolved_by_user_id", models.UUIDField(blank=True, null=True)),
                ("resolved_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "loan",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT, related_name="fines", to="library.loan"
                    ),
                ),
                (
                    "student_fee",
                    models.OneToOneField(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="library_fine",
                        to="fees.studentfee",
                    ),
                ),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.AddIndex(
            model_name="book",
            index=models.Index(fields=["isbn"], name="library_book_isbn_idx"),
        ),
        migrations.AddConstraint(
            model_name="book",
            constraint=models.CheckConstraint(
                condition=models.Q(("price__isnull", True), ("price__gte", 0), _connector="OR"),
                name="library_book_price_not_negative",
            ),
        ),
        migrations.AddConstraint(
            model_name="librarysettings",
            constraint=models.CheckConstraint(condition=models.Q(("singleton", True)), name="library_settings_singleton_true"),
        ),
        migrations.AddConstraint(
            model_name="librarysettings",
            constraint=models.CheckConstraint(
                condition=models.Q(("fine_per_day__gte", 0)), name="library_settings_fine_not_negative"
            ),
        ),
        migrations.AddIndex(
            model_name="loan",
            index=models.Index(fields=["due_on"], name="library_loan_due_idx"),
        ),
        migrations.AddConstraint(
            model_name="loan",
            constraint=models.UniqueConstraint(
                condition=models.Q(("returned_on__isnull", True)),
                fields=("copy",),
                name="library_one_open_loan_per_copy",
            ),
        ),
        migrations.AddConstraint(
            model_name="loan",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    models.Q(("student__isnull", False), ("staff__isnull", True)),
                    models.Q(("student__isnull", True), ("staff__isnull", False)),
                    _connector="OR",
                ),
                name="library_loan_exactly_one_borrower",
            ),
        ),
        migrations.AddConstraint(
            model_name="loan",
            constraint=models.CheckConstraint(
                condition=models.Q(("due_on__gte", models.F("issued_on"))), name="library_loan_due_after_issue"
            ),
        ),
        migrations.AddConstraint(
            model_name="loan",
            constraint=models.CheckConstraint(
                condition=models.Q(("returned_on__isnull", True), ("returned_on__gte", models.F("issued_on")), _connector="OR"),
                name="library_loan_return_after_issue",
            ),
        ),
        migrations.AddConstraint(
            model_name="fine",
            constraint=models.UniqueConstraint(fields=("loan", "kind"), name="library_one_fine_per_loan_and_kind"),
        ),
        migrations.AddConstraint(
            model_name="fine",
            constraint=models.CheckConstraint(condition=models.Q(("amount__gt", 0)), name="library_fine_amount_positive"),
        ),
    ]
