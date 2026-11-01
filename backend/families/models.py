from django.db import models
import uuid


class Parent(models.Model):
    """
    Stores professional and specific demographic data for parents.
    Personal data is stored in the linked Profile.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    profile = models.OneToOneField(
        "profiles.Profile", on_delete=models.CASCADE, related_name="parent_record"
    )

    occupation = models.CharField(max_length=100, blank=True)
    office_address = models.TextField(blank=True)
    income_level = models.CharField(max_length=50, blank=True)

    # The parent agreed to receive fee and attendance messages on WhatsApp (their profile phone number). The
    # school records that consent; nothing is sent to a parent without it.
    whatsapp_opt_in = models.BooleanField(default=False)
    whatsapp_opt_in_at = models.DateTimeField(null=True, blank=True)

    def save(self, *args, **kwargs):
        from django.utils import timezone

        if self.whatsapp_opt_in and self.whatsapp_opt_in_at is None:
            self.whatsapp_opt_in_at = timezone.now()
        elif not self.whatsapp_opt_in:
            self.whatsapp_opt_in_at = None
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Parent: {self.profile.first_name}"


class StudentParentRelation(models.Model):
    """
    Many-to-Many relationship table with metadata.
    Links students to parents/guardians.
    """

    student = models.ForeignKey(
        "students.Student", on_delete=models.CASCADE, related_name="parent_links"
    )
    parent = models.ForeignKey(
        Parent, on_delete=models.CASCADE, related_name="student_links"
    )

    relation_type = models.CharField(
        max_length=20,
        choices=[
            ("father", "Father"),
            ("mother", "Mother"),
            ("guardian", "Guardian"),
            ("brother", "Brother"),
            ("sister", "Sister"),
            ("other", "Other"),
        ],
    )

    is_primary_contact = models.BooleanField(default=False)
    can_pickup = models.BooleanField(default=True)

    class Meta:
        unique_together = ("student", "parent")
