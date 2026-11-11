"""Student health records: standing medical information, and incidents at school."""
import uuid

from django.db import models


class StudentHealthProfile(models.Model):
    """What staff must know to keep a student safe. One per student; blood group lives on the Profile."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    student = models.OneToOneField("students.Student", on_delete=models.CASCADE, related_name="health_profile")
    allergies = models.TextField(blank=True, help_text="Food, medicine or other allergies and how severe they are.")
    medical_conditions = models.TextField(blank=True, help_text="Asthma, diabetes, epilepsy and similar.")
    medications = models.TextField(blank=True, help_text="Regular medicines and when they are taken.")
    dietary_notes = models.TextField(blank=True)
    doctor_name = models.CharField(max_length=120, blank=True)
    doctor_phone = models.CharField(max_length=20, blank=True)
    notes = models.TextField(blank=True)
    updated_by = models.ForeignKey("staff.StaffMember", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Health profile {self.student_id}"

    @property
    def has_alert(self):
        return bool(self.allergies.strip() or self.medical_conditions.strip())


INCIDENT_KIND_CHOICES = [
    ("illness", "Illness"),
    ("injury", "Injury"),
    ("allergic_reaction", "Allergic reaction"),
    ("medication", "Medicine given"),
    ("other", "Other"),
]


class HealthIncident(models.Model):
    """Something that happened to a student's health at school. Kept as a record: never deleted."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    student = models.ForeignKey("students.Student", on_delete=models.PROTECT, related_name="health_incidents")
    occurred_at = models.DateTimeField()
    kind = models.CharField(max_length=20, choices=INCIDENT_KIND_CHOICES)
    description = models.TextField()
    action_taken = models.TextField(blank=True)
    sent_home = models.BooleanField(default=False)
    parent_informed = models.BooleanField(default=False)
    recorded_by = models.ForeignKey("staff.StaffMember", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-occurred_at"]
        indexes = [models.Index(fields=["student", "-occurred_at"], name="health_incident_student_idx")]

    def __str__(self):
        return f"{self.get_kind_display()} {self.student_id} {self.occurred_at:%Y-%m-%d}"
