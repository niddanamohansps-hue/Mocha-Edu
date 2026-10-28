"""
The homework diary: a teacher sets homework for one section and subject; each student (or a parent for
them) can mark it seen and done. Files attached to homework are virus-scanned like admission documents.
"""
import uuid

from django.db import models


class Homework(models.Model):
    ACTIVE, CANCELLED = "active", "cancelled"
    STATUS_CHOICES = [(ACTIVE, "Active"), (CANCELLED, "Cancelled")]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    section = models.ForeignKey("academics.Section", on_delete=models.CASCADE, related_name="homework")
    subject = models.ForeignKey("academics.Subject", on_delete=models.CASCADE, related_name="homework")
    title = models.CharField(max_length=200)
    details = models.TextField(blank=True)
    assigned_on = models.DateField()
    due_date = models.DateField()
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=ACTIVE)
    created_by = models.ForeignKey("staff.StaffMember", on_delete=models.SET_NULL, null=True, blank=True,
                                   related_name="homework_set")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-assigned_on", "-created_at"]
        indexes = [
            models.Index(fields=["section", "due_date"], name="homework_section_due_idx"),
            models.Index(fields=["assigned_on"], name="homework_assigned_idx"),
        ]

    def __str__(self):
        return f"{self.title} ({self.section}, due {self.due_date})"


def _attachment_path(instance, filename):
    return f"homework/{instance.homework_id}/{uuid.uuid4().hex}-{filename[-80:]}"


class HomeworkAttachment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    homework = models.ForeignKey(Homework, on_delete=models.CASCADE, related_name="attachments")
    file = models.FileField(upload_to=_attachment_path)
    original_name = models.CharField(max_length=255)
    size = models.PositiveIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]


class HomeworkProgress(models.Model):
    """One student's progress on one homework: when it was first seen and when it was marked done."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    homework = models.ForeignKey(Homework, on_delete=models.CASCADE, related_name="progress")
    student = models.ForeignKey("students.Student", on_delete=models.CASCADE, related_name="homework_progress")
    seen_at = models.DateTimeField(null=True, blank=True)
    done_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["homework", "student"], name="homework_progress_unique")]
