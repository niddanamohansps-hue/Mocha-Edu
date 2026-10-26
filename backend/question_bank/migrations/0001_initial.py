import uuid
from decimal import Decimal

import django.core.validators
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("academics", "0003_calendarevent"),
        ("staff", "0002_leavetype_leaveapplication_leaveapproval_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="Chapter",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("name", models.CharField(max_length=150)),
                ("order", models.PositiveSmallIntegerField(default=1)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "subject",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE, related_name="chapters", to="academics.subject"
                    ),
                ),
            ],
            options={"ordering": ["subject", "order", "name"]},
        ),
        migrations.CreateModel(
            name="Topic",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("name", models.CharField(max_length=150)),
                ("order", models.PositiveSmallIntegerField(default=1)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "chapter",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE, related_name="topics", to="question_bank.chapter"
                    ),
                ),
            ],
            options={"ordering": ["chapter", "order", "name"]},
        ),
        migrations.CreateModel(
            name="SubjectReviewer",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "staff",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="question_review_subjects",
                        to="staff.staffmember",
                    ),
                ),
                (
                    "subject",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="question_reviewers",
                        to="academics.subject",
                    ),
                ),
            ],
            options={"ordering": ["subject", "staff"]},
        ),
        migrations.CreateModel(
            name="Question",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                (
                    "question_type",
                    models.CharField(
                        choices=[
                            ("mcq", "Multiple choice (one answer)"),
                            ("multi_select", "Multiple choice (several answers)"),
                            ("true_false", "True or false"),
                            ("short", "Short answer"),
                            ("long", "Long answer"),
                            ("case_based", "Case-based"),
                        ],
                        max_length=20,
                    ),
                ),
                (
                    "difficulty",
                    models.CharField(
                        choices=[("easy", "Easy"), ("medium", "Medium"), ("hard", "Hard")],
                        default="medium",
                        max_length=10,
                    ),
                ),
                (
                    "marks",
                    models.DecimalField(
                        decimal_places=2,
                        max_digits=5,
                        validators=[django.core.validators.MinValueValidator(Decimal("0.5"))],
                    ),
                ),
                ("body", models.TextField()),
                ("options", models.JSONField(blank=True, default=list)),
                ("answer", models.TextField(blank=True, help_text="The expected or model answer.")),
                ("explanation", models.TextField(blank=True)),
                ("marking_scheme", models.TextField(blank=True, help_text="How marks are given, for written answers.")),
                ("learning_outcome", models.CharField(blank=True, max_length=255)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("draft", "Draft"),
                            ("submitted", "Waiting for review"),
                            ("changes_requested", "Changes requested"),
                            ("approved", "Approved"),
                            ("rejected", "Rejected"),
                            ("archived", "Archived"),
                        ],
                        default="draft",
                        max_length=20,
                    ),
                ),
                ("version", models.PositiveIntegerField(default=1)),
                ("content_hash", models.CharField(db_index=True, max_length=64)),
                ("created_by_user_id", models.UUIDField()),
                ("submitted_at", models.DateTimeField(blank=True, null=True)),
                ("decided_at", models.DateTimeField(blank=True, null=True)),
                ("decided_by_user_id", models.UUIDField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "author",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="authored_questions",
                        to="staff.staffmember",
                    ),
                ),
                (
                    "chapter",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="questions",
                        to="question_bank.chapter",
                    ),
                ),
                (
                    "subject",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT, related_name="questions", to="academics.subject"
                    ),
                ),
                (
                    "topic",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="questions",
                        to="question_bank.topic",
                    ),
                ),
            ],
            options={"ordering": ["-updated_at"]},
        ),
        migrations.CreateModel(
            name="QuestionVersion",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("number", models.PositiveIntegerField()),
                ("content", models.JSONField()),
                ("created_by_user_id", models.UUIDField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "question",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE, related_name="versions", to="question_bank.question"
                    ),
                ),
            ],
            options={"ordering": ["question", "-number"]},
        ),
        migrations.CreateModel(
            name="QuestionReview",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("version", models.PositiveIntegerField()),
                (
                    "decision",
                    models.CharField(
                        choices=[
                            ("approved", "Approved"),
                            ("changes_requested", "Changes requested"),
                            ("rejected", "Rejected"),
                        ],
                        max_length=20,
                    ),
                ),
                ("comment", models.TextField(blank=True)),
                ("reviewer_user_id", models.UUIDField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "question",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE, related_name="reviews", to="question_bank.question"
                    ),
                ),
                (
                    "reviewer",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="question_reviews",
                        to="staff.staffmember",
                    ),
                ),
            ],
            options={"ordering": ["question", "-created_at"]},
        ),
        migrations.AddConstraint(
            model_name="chapter",
            constraint=models.UniqueConstraint(fields=("subject", "name"), name="qb_chapter_unique_name"),
        ),
        migrations.AddConstraint(
            model_name="topic",
            constraint=models.UniqueConstraint(fields=("chapter", "name"), name="qb_topic_unique_name"),
        ),
        migrations.AddConstraint(
            model_name="subjectreviewer",
            constraint=models.UniqueConstraint(fields=("subject", "staff"), name="qb_reviewer_unique"),
        ),
        migrations.AddIndex(
            model_name="question",
            index=models.Index(fields=["subject", "status"], name="qb_question_subject_status"),
        ),
        migrations.AddIndex(
            model_name="question",
            index=models.Index(fields=["created_by_user_id", "status"], name="qb_question_author_status"),
        ),
        migrations.AddConstraint(
            model_name="question",
            constraint=models.CheckConstraint(condition=models.Q(("marks__gt", 0)), name="qb_question_marks_positive"),
        ),
        migrations.AddConstraint(
            model_name="question",
            constraint=models.CheckConstraint(condition=models.Q(("version__gte", 1)), name="qb_question_version_positive"),
        ),
        migrations.AddConstraint(
            model_name="questionversion",
            constraint=models.UniqueConstraint(fields=("question", "number"), name="qb_version_unique_number"),
        ),
    ]
