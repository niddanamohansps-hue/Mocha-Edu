import uuid

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("examinations", "0002_examination_academic_year_ref_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="examination",
            name="publication_requested_by_user_id",
            field=models.UUIDField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="examination",
            name="publication_requested_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="examination",
            name="published_by_user_id",
            field=models.UUIDField(blank=True, null=True),
        ),
        migrations.CreateModel(
            name="ExaminationSettings",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("singleton", models.BooleanField(default=True, editable=False, unique=True)),
                ("require_separate_publisher", models.BooleanField(default=False)),
                ("updated_by_user_id", models.UUIDField(blank=True, null=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"verbose_name_plural": "Examination settings"},
        ),
        migrations.AddConstraint(
            model_name="examinationsettings",
            constraint=models.CheckConstraint(condition=models.Q(("singleton", True)), name="exam_settings_singleton_true"),
        ),
    ]
