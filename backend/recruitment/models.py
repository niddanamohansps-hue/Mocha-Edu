import secrets
import uuid

from django.core.validators import FileExtensionValidator
from django.db import models


class JobOpening(models.Model):
    """A position the school is hiring for."""

    class PositionType(models.TextChoices):
        INSTRUCTOR = "instructor", "Instructor (teaching)"
        STAFF = "staff", "General staff"

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        OPEN = "open", "Open"
        CLOSED = "closed", "Closed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=200, help_text="e.g. 'Mathematics Teacher (Grades 6-8)'")
    position_type = models.CharField(max_length=20, choices=PositionType.choices)
    department = models.CharField(max_length=100, blank=True)
    specialization = models.CharField(
        max_length=100, blank=True, help_text="Subject or area, used when the hire becomes an instructor"
    )
    vacancies = models.PositiveIntegerField(default=1)
    description = models.TextField(blank=True)
    requirements = models.TextField(blank=True)
    min_experience_years = models.PositiveIntegerField(default=0)
    last_date = models.DateField(null=True, blank=True, help_text="Last day applications are accepted")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    created_by_id = models.UUIDField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.title} ({self.status})"


def new_reference():
    return "JOB-" + secrets.token_hex(4).upper()


class Applicant(models.Model):
    """One person's application to one opening, moving through the hiring pipeline."""

    class Stage(models.TextChoices):
        APPLIED = "applied", "Applied"
        SHORTLISTED = "shortlisted", "Shortlisted"
        INTERVIEW = "interview", "Interview"
        OFFERED = "offered", "Offered"
        HIRED = "hired", "Hired"
        REJECTED = "rejected", "Rejected"

    class Gender(models.TextChoices):
        MALE = "male", "Male"
        FEMALE = "female", "Female"
        OTHER = "other", "Other"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    # PROTECT: an opening with applicants is closed, never deleted, so the hiring record survives.
    opening = models.ForeignKey(JobOpening, on_delete=models.PROTECT, related_name="applicants")
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=20, blank=True)
    gender = models.CharField(max_length=10, choices=Gender.choices, blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    address = models.TextField(blank=True)
    qualification = models.CharField(max_length=255, blank=True)
    experience_years = models.PositiveIntegerField(default=0)
    current_employer = models.CharField(max_length=200, blank=True)
    expected_salary = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    resume = models.FileField(
        upload_to="recruitment_resumes/",
        null=True,
        blank=True,
        validators=[FileExtensionValidator(["pdf", "doc", "docx"])],
    )
    cover_note = models.TextField(blank=True)
    source = models.CharField(max_length=100, blank=True, help_text="Where the applicant heard of the job")

    # What the candidate quotes to check their application. The secret that goes with it is stored only as a hash.
    reference = models.CharField(max_length=20, blank=True, default="", editable=False)
    access_token_hash = models.CharField(max_length=64, blank=True, default="", editable=False)

    stage = models.CharField(max_length=20, choices=Stage.choices, default=Stage.APPLIED)
    stage_changed_at = models.DateTimeField(auto_now_add=True)
    rejection_reason = models.TextField(blank=True)
    hired_staff = models.OneToOneField(
        "staff.StaffMember",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="recruitment_application",
    )
    created_by_id = models.UUIDField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            # The same person applying twice to one opening is one application. Blank emails are exempt.
            models.UniqueConstraint(
                fields=["opening", "email"],
                condition=~models.Q(email=""),
                name="uniq_applicant_email_per_opening",
            ),
            models.UniqueConstraint(
                fields=["reference"],
                condition=~models.Q(reference=""),
                name="uniq_applicant_reference",
            ),
        ]

    def __str__(self):
        return f"{self.first_name} {self.last_name} -> {self.opening_id} ({self.stage})"

    def save(self, *args, **kwargs):
        if not self.reference:
            self.reference = new_reference()
        super().save(*args, **kwargs)

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}".strip()


class ApplicantEvent(models.Model):
    """Append-only trail of stage changes, so the pipeline can always be explained afterwards."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    applicant = models.ForeignKey(Applicant, on_delete=models.CASCADE, related_name="events")
    from_stage = models.CharField(max_length=20, blank=True)
    to_stage = models.CharField(max_length=20)
    note = models.TextField(blank=True)
    actor_id = models.UUIDField(null=True, blank=True)
    actor_name = models.CharField(max_length=150, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]


class Interview(models.Model):
    """One interview round for an applicant."""

    class Mode(models.TextChoices):
        IN_PERSON = "in_person", "In person"
        ONLINE = "online", "Online"
        PHONE = "phone", "Phone"

    class Status(models.TextChoices):
        SCHEDULED = "scheduled", "Scheduled"
        COMPLETED = "completed", "Completed"
        CANCELLED = "cancelled", "Cancelled"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    applicant = models.ForeignKey(Applicant, on_delete=models.CASCADE, related_name="interviews")
    round_name = models.CharField(max_length=100, default="Interview")
    scheduled_at = models.DateTimeField()
    mode = models.CharField(max_length=20, choices=Mode.choices, default=Mode.IN_PERSON)
    location_or_url = models.CharField(max_length=255, blank=True)
    interviewer = models.ForeignKey(
        "staff.StaffMember",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="recruitment_interviews",
    )
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.SCHEDULED)
    score = models.DecimalField(max_digits=4, decimal_places=1, null=True, blank=True, help_text="0 to 10")
    feedback = models.TextField(blank=True)
    created_by_id = models.UUIDField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["scheduled_at"]


class InterviewPanelist(models.Model):
    """One panel member's own score and comment for an interview."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    interview = models.ForeignKey(Interview, on_delete=models.CASCADE, related_name="panelists")
    # PROTECT: a staff record that has judged a candidate is part of the hiring record and must not vanish.
    staff = models.ForeignKey("staff.StaffMember", on_delete=models.PROTECT, related_name="interview_panels")
    score = models.DecimalField(max_digits=4, decimal_places=1, null=True, blank=True, help_text="0 to 10")
    feedback = models.TextField(blank=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]
        constraints = [
            models.UniqueConstraint(fields=["interview", "staff"], name="uniq_panelist_per_interview"),
        ]
