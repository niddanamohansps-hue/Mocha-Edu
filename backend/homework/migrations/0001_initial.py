import uuid

import django.db.models.deletion
from django.db import migrations, models

import homework.models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("academics", "0003_calendarevent"),
        ("staff", "0002_leavetype_leaveapplication_leaveapproval_and_more"),
        ("students", "0007_admissiondocument_scan_details_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="Homework",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("title", models.CharField(max_length=200)),
                ("details", models.TextField(blank=True)),
                ("assigned_on", models.DateField()),
                ("due_date", models.DateField()),
                ("status", models.CharField(choices=[("active", "Active"), ("cancelled", "Cancelled")], default="active", max_length=10)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="homework_set", to="staff.staffmember")),
                ("section", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="homework", to="academics.section")),
                ("subject", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="homework", to="academics.subject")),
            ],
            options={
                "ordering": ["-assigned_on", "-created_at"],
                "indexes": [
                    models.Index(fields=["section", "due_date"], name="homework_section_due_idx"),
                    models.Index(fields=["assigned_on"], name="homework_assigned_idx"),
                ],
            },
        ),
        migrations.CreateModel(
            name="HomeworkAttachment",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("file", models.FileField(upload_to=homework.models._attachment_path)),
                ("original_name", models.CharField(max_length=255)),
                ("size", models.PositiveIntegerField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("homework", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="attachments", to="homework.homework")),
            ],
            options={"ordering": ["created_at"]},
        ),
        migrations.CreateModel(
            name="HomeworkProgress",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("seen_at", models.DateTimeField(blank=True, null=True)),
                ("done_at", models.DateTimeField(blank=True, null=True)),
                ("homework", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="progress", to="homework.homework")),
                ("student", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="homework_progress", to="students.student")),
            ],
            options={
                "constraints": [models.UniqueConstraint(fields=("homework", "student"), name="homework_progress_unique")],
            },
        ),
    ]
