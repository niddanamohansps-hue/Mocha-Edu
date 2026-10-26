import uuid
from decimal import Decimal

import django.core.validators
import django.db.models.deletion
from django.db import migrations, models

QUESTION_TYPES = [
    ("mcq", "Multiple choice (one answer)"),
    ("multi_select", "Multiple choice (several answers)"),
    ("true_false", "True or false"),
    ("short", "Short answer"),
    ("long", "Long answer"),
    ("case_based", "Case-based"),
]


class Migration(migrations.Migration):

    dependencies = [
        ("academics", "0003_calendarevent"),
        ("examinations", "0002_examination_academic_year_ref_and_more"),
        ("question_bank", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="QuestionPaper",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("set_label", models.CharField(default="A", max_length=10)),
                ("title", models.CharField(max_length=200)),
                ("instructions", models.TextField(blank=True)),
                (
                    "total_marks",
                    models.DecimalField(
                        decimal_places=2,
                        max_digits=6,
                        validators=[django.core.validators.MinValueValidator(Decimal("1"))],
                    ),
                ),
                (
                    "duration_minutes",
                    models.PositiveSmallIntegerField(validators=[django.core.validators.MinValueValidator(1)]),
                ),
                (
                    "allow_shared_questions",
                    models.BooleanField(default=False, help_text="Allow questions also used in another set of the same paper."),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("draft", "Draft"),
                            ("submitted", "Waiting for approval"),
                            ("approved", "Approved"),
                            ("released", "Released"),
                            ("withdrawn", "Withdrawn"),
                        ],
                        default="draft",
                        max_length=10,
                    ),
                ),
                ("release_at", models.DateTimeField(blank=True, help_text="Released automatically from this time.", null=True)),
                ("frozen_content", models.JSONField(blank=True, null=True)),
                ("review_comment", models.TextField(blank=True)),
                ("withdraw_reason", models.CharField(blank=True, max_length=255)),
                ("prepared_by_user_id", models.UUIDField()),
                ("submitted_at", models.DateTimeField(blank=True, null=True)),
                ("approved_by_user_id", models.UUIDField(blank=True, null=True)),
                ("approved_at", models.DateTimeField(blank=True, null=True)),
                ("released_at", models.DateTimeField(blank=True, null=True)),
                ("withdrawn_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "examination",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="question_papers",
                        to="examinations.examination",
                    ),
                ),
                (
                    "subject",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT, related_name="question_papers", to="academics.subject"
                    ),
                ),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.CreateModel(
            name="PaperSection",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("order", models.PositiveSmallIntegerField(default=1)),
                ("title", models.CharField(max_length=100)),
                ("instructions", models.CharField(blank=True, max_length=500)),
                (
                    "paper",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE, related_name="sections", to="question_bank.questionpaper"
                    ),
                ),
            ],
            options={"ordering": ["paper", "order"]},
        ),
        migrations.CreateModel(
            name="BlueprintRule",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("count", models.PositiveSmallIntegerField(validators=[django.core.validators.MinValueValidator(1)])),
                ("question_type", models.CharField(blank=True, choices=QUESTION_TYPES, max_length=20)),
                (
                    "difficulty",
                    models.CharField(blank=True, choices=[("easy", "Easy"), ("medium", "Medium"), ("hard", "Hard")], max_length=10),
                ),
                (
                    "chapter",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="blueprint_rules",
                        to="question_bank.chapter",
                    ),
                ),
                (
                    "section",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE, related_name="rules", to="question_bank.papersection"
                    ),
                ),
            ],
            options={"ordering": ["section", "id"]},
        ),
        migrations.CreateModel(
            name="PaperQuestion",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("question_version", models.PositiveIntegerField()),
                ("order", models.PositiveSmallIntegerField(default=1)),
                ("marks", models.DecimalField(decimal_places=2, max_digits=5)),
                (
                    "paper",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE, related_name="items", to="question_bank.questionpaper"
                    ),
                ),
                (
                    "question",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT, related_name="paper_items", to="question_bank.question"
                    ),
                ),
                (
                    "section",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE, related_name="items", to="question_bank.papersection"
                    ),
                ),
            ],
            options={"ordering": ["section__order", "order"]},
        ),
        migrations.CreateModel(
            name="PaperAccessLog",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("user_id", models.UUIDField()),
                (
                    "kind",
                    models.CharField(
                        choices=[("paper", "Opened the paper"), ("answer_key", "Opened the answer key")], max_length=12
                    ),
                ),
                ("status_at_access", models.CharField(max_length=10)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "paper",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE, related_name="access_log", to="question_bank.questionpaper"
                    ),
                ),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.AddConstraint(
            model_name="questionpaper",
            constraint=models.UniqueConstraint(
                condition=models.Q(("status", "withdrawn"), _negated=True),
                fields=("examination", "subject", "set_label"),
                name="qb_paper_unique_live_set",
            ),
        ),
        migrations.AddConstraint(
            model_name="questionpaper",
            constraint=models.CheckConstraint(condition=models.Q(("total_marks__gt", 0)), name="qb_paper_marks_positive"),
        ),
        migrations.AddConstraint(
            model_name="papersection",
            constraint=models.UniqueConstraint(fields=("paper", "order"), name="qb_section_unique_order"),
        ),
        migrations.AddConstraint(
            model_name="blueprintrule",
            constraint=models.CheckConstraint(condition=models.Q(("count__gte", 1)), name="qb_rule_count_positive"),
        ),
        migrations.AddConstraint(
            model_name="paperquestion",
            constraint=models.UniqueConstraint(fields=("paper", "question"), name="qb_paper_question_once"),
        ),
    ]
