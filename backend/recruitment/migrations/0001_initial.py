import uuid

import django.core.validators
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("staff", "0002_leavetype_leaveapplication_leaveapproval_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="JobOpening",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("title", models.CharField(help_text="e.g. 'Mathematics Teacher (Grades 6-8)'", max_length=200)),
                (
                    "position_type",
                    models.CharField(
                        choices=[("instructor", "Instructor (teaching)"), ("staff", "General staff")],
                        max_length=20,
                    ),
                ),
                ("department", models.CharField(blank=True, max_length=100)),
                (
                    "specialization",
                    models.CharField(
                        blank=True,
                        help_text="Subject or area, used when the hire becomes an instructor",
                        max_length=100,
                    ),
                ),
                ("vacancies", models.PositiveIntegerField(default=1)),
                ("description", models.TextField(blank=True)),
                ("requirements", models.TextField(blank=True)),
                ("min_experience_years", models.PositiveIntegerField(default=0)),
                (
                    "last_date",
                    models.DateField(blank=True, help_text="Last day applications are accepted", null=True),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[("draft", "Draft"), ("open", "Open"), ("closed", "Closed")],
                        default="draft",
                        max_length=20,
                    ),
                ),
                ("created_by_id", models.UUIDField(blank=True, null=True)),
                ("closed_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
        migrations.CreateModel(
            name="Applicant",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("first_name", models.CharField(max_length=100)),
                ("last_name", models.CharField(max_length=100)),
                ("email", models.EmailField(blank=True, max_length=254)),
                ("phone", models.CharField(blank=True, max_length=20)),
                (
                    "gender",
                    models.CharField(
                        blank=True,
                        choices=[("male", "Male"), ("female", "Female"), ("other", "Other")],
                        max_length=10,
                    ),
                ),
                ("date_of_birth", models.DateField(blank=True, null=True)),
                ("address", models.TextField(blank=True)),
                ("qualification", models.CharField(blank=True, max_length=255)),
                ("experience_years", models.PositiveIntegerField(default=0)),
                ("current_employer", models.CharField(blank=True, max_length=200)),
                (
                    "expected_salary",
                    models.DecimalField(blank=True, decimal_places=2, max_digits=12, null=True),
                ),
                (
                    "resume",
                    models.FileField(
                        blank=True,
                        null=True,
                        upload_to="recruitment_resumes/",
                        validators=[django.core.validators.FileExtensionValidator(["pdf", "doc", "docx"])],
                    ),
                ),
                ("cover_note", models.TextField(blank=True)),
                (
                    "source",
                    models.CharField(blank=True, help_text="Where the applicant heard of the job", max_length=100),
                ),
                (
                    "stage",
                    models.CharField(
                        choices=[
                            ("applied", "Applied"),
                            ("shortlisted", "Shortlisted"),
                            ("interview", "Interview"),
                            ("offered", "Offered"),
                            ("hired", "Hired"),
                            ("rejected", "Rejected"),
                        ],
                        default="applied",
                        max_length=20,
                    ),
                ),
                ("stage_changed_at", models.DateTimeField(auto_now_add=True)),
                ("rejection_reason", models.TextField(blank=True)),
                ("created_by_id", models.UUIDField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "hired_staff",
                    models.OneToOneField(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="recruitment_application",
                        to="staff.staffmember",
                    ),
                ),
                (
                    "opening",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="applicants",
                        to="recruitment.jobopening",
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
        migrations.CreateModel(
            name="ApplicantEvent",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("from_stage", models.CharField(blank=True, max_length=20)),
                ("to_stage", models.CharField(max_length=20)),
                ("note", models.TextField(blank=True)),
                ("actor_id", models.UUIDField(blank=True, null=True)),
                ("actor_name", models.CharField(blank=True, max_length=150)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "applicant",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="events",
                        to="recruitment.applicant",
                    ),
                ),
            ],
            options={
                "ordering": ["created_at"],
            },
        ),
        migrations.CreateModel(
            name="Interview",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("round_name", models.CharField(default="Interview", max_length=100)),
                ("scheduled_at", models.DateTimeField()),
                (
                    "mode",
                    models.CharField(
                        choices=[("in_person", "In person"), ("online", "Online"), ("phone", "Phone")],
                        default="in_person",
                        max_length=20,
                    ),
                ),
                ("location_or_url", models.CharField(blank=True, max_length=255)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("scheduled", "Scheduled"),
                            ("completed", "Completed"),
                            ("cancelled", "Cancelled"),
                        ],
                        default="scheduled",
                        max_length=20,
                    ),
                ),
                (
                    "score",
                    models.DecimalField(blank=True, decimal_places=1, help_text="0 to 10", max_digits=4, null=True),
                ),
                ("feedback", models.TextField(blank=True)),
                ("created_by_id", models.UUIDField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "applicant",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="interviews",
                        to="recruitment.applicant",
                    ),
                ),
                (
                    "interviewer",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="recruitment_interviews",
                        to="staff.staffmember",
                    ),
                ),
            ],
            options={
                "ordering": ["scheduled_at"],
            },
        ),
        migrations.AddConstraint(
            model_name="applicant",
            constraint=models.UniqueConstraint(
                condition=models.Q(("email", ""), _negated=True),
                fields=("opening", "email"),
                name="uniq_applicant_email_per_opening",
            ),
        ),
    ]
