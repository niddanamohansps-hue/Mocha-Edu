import uuid

from django.core.exceptions import ValidationError
from django.db import models


class ExamType(models.Model):
    """
    Configurable exam category (e.g. "Mid-Term", "Unit Test", "Annual
    Examination"). Deliberately NOT a hardcoded Python choices list - naming
    varies too much by school/region to fix in code, and unlike Attendance's
    status choices, an exam type carries no differential system behavior.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100)
    order = models.IntegerField(default=1)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["order", "name"]

    def __str__(self):
        return self.name


class Examination(models.Model):
    """
    A named examination event (e.g. "Mid-Term 2026"). academic_year is a
    plain string, matching the project-wide convention already used by
    StudentLevel/AttendanceSession/TimetableEntry - no dedicated AcademicYear
    model exists or is introduced here.

    Publication is whole-exam, not per-schedule: once is_published=True, an
    ExamResult snapshot exists per participating student and must not be
    silently recalculated.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    academic_year = models.CharField(max_length=20)
    academic_year_ref = models.ForeignKey(
        "academics.AcademicYear",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
    )
    name = models.CharField(max_length=200)
    exam_type = models.ForeignKey(ExamType, on_delete=models.PROTECT, related_name="examinations")
    start_date = models.DateField()
    end_date = models.DateField()

    is_published = models.BooleanField(default=False)
    published_at = models.DateTimeField(null=True, blank=True)
    # Two-person publishing (see ExaminationSettings): who asked for the results to be published, and when.
    publication_requested_by_user_id = models.UUIDField(null=True, blank=True)
    publication_requested_at = models.DateTimeField(null=True, blank=True)
    published_by_user_id = models.UUIDField(null=True, blank=True)

    # The date sheet is announced to students and parents on request. Each announcement has a number, so sending
    # it again after a change notifies everyone again, while a repeated run of the same one never does.
    date_sheet_published_at = models.DateTimeField(null=True, blank=True)
    date_sheet_version = models.PositiveIntegerField(default=0)

    # The day by which teachers should have entered every paper's marks. Optional; drives the progress board and
    # the automatic reminders.
    marks_due_date = models.DateField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-start_date"]

    def __str__(self):
        return f"{self.name} ({self.academic_year})"


class ExamSchedule(models.Model):
    """
    Examination + Subject + Section, with its own authoritative date/time -
    NOT a reference to timetable.TimetableEntry, which represents a
    recurring WEEKLY template, not a one-off dated event. Regular timetable
    entries are not authoritative on examination days (classes are commonly
    suspended), so exam scheduling is deliberately independent of them.

    timetable.Room and timetable.Period are reused directly (both optional -
    an exam may run outside normal periods/rooms), never duplicated.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    examination = models.ForeignKey(Examination, on_delete=models.CASCADE, related_name="schedules")
    academic_year = models.CharField(max_length=20)
    academic_year_ref = models.ForeignKey(
        "academics.AcademicYear",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
    )
    subject = models.ForeignKey(
        "academics.Subject", on_delete=models.CASCADE, related_name="exam_schedules"
    )
    section = models.ForeignKey(
        "academics.Section", on_delete=models.CASCADE, related_name="exam_schedules"
    )

    date = models.DateField()
    start_time = models.TimeField()
    end_time = models.TimeField()

    period = models.ForeignKey(
        "timetable.Period", on_delete=models.SET_NULL, null=True, blank=True, related_name="exam_schedules"
    )
    room = models.ForeignKey(
        "timetable.Room", on_delete=models.SET_NULL, null=True, blank=True, related_name="exam_schedules"
    )

    max_marks = models.DecimalField(max_digits=6, decimal_places=2)
    pass_marks = models.DecimalField(max_digits=6, decimal_places=2)

    is_locked = models.BooleanField(default=False)
    locked_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("examination", "subject", "section")
        ordering = ["date", "start_time"]

    def __str__(self):
        return f"{self.examination} - {self.subject} - {self.section}"


class ExamScheduleComponent(models.Model):
    """
    Sub-component of an ExamSchedule (e.g. Theory, Practical, Internal Assessment).
    Allows schools to define custom component splits with independent maximum
    and passing marks, plus optional separate pass enforcement.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    exam_schedule = models.ForeignKey(
        ExamSchedule, on_delete=models.CASCADE, related_name="components"
    )
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=20)
    max_marks = models.DecimalField(max_digits=6, decimal_places=2)
    pass_marks = models.DecimalField(max_digits=6, decimal_places=2)
    is_theory = models.BooleanField(default=True)
    requires_separate_pass = models.BooleanField(
        default=False,
        help_text="If True, student must score >= pass_marks in this component to pass the subject.",
    )
    order = models.PositiveIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["order", "name"]
        unique_together = ("exam_schedule", "code")

    def __str__(self):
        return f"{self.exam_schedule} - {self.name} ({self.code})"

    def clean(self):
        if self.max_marks is not None and self.max_marks <= 0:
            raise ValidationError({"max_marks": "Maximum marks must be greater than zero."})
        if self.pass_marks is not None and self.max_marks is not None:
            if self.pass_marks > self.max_marks:
                raise ValidationError({"pass_marks": "Pass marks cannot exceed maximum marks."})
            if self.pass_marks < 0:
                raise ValidationError({"pass_marks": "Pass marks cannot be negative."})


class ExamMark(models.Model):
    """
    Raw, source-of-truth marks for one student in one ExamSchedule.

    marks_obtained is nullable: NULL + is_absent=False means "not yet
    graded"; is_absent=True means the student was absent. These two states
    must remain distinguishable - NULL is never silently treated as absent.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    exam_schedule = models.ForeignKey(ExamSchedule, on_delete=models.CASCADE, related_name="marks")
    student = models.ForeignKey(
        "students.Student", on_delete=models.CASCADE, related_name="exam_marks"
    )
    class Attendance(models.TextChoices):
        PRESENT = "present", "Present"
        ABSENT = "absent", "Absent"
        MEDICAL = "medical", "Absent (medical)"
        MALPRACTICE = "malpractice", "Malpractice"
        EXEMPT = "exempt", "Exempt"

    # Attendance values that count as "did not sit": no marks, and the subject is failed.
    NOT_SAT = ("absent", "medical", "malpractice")

    marks_obtained = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    # is_absent is kept in step with attendance (absent, medical and malpractice) for older readers.
    is_absent = models.BooleanField(default=False)
    attendance = models.CharField(max_length=12, choices=Attendance.choices, default=Attendance.PRESENT)
    # Grace marks are added on top of marks_obtained, never beyond the schedule's maximum.
    grace_marks = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    remarks = models.CharField(max_length=255, blank=True)

    entered_by = models.ForeignKey(
        "staff.StaffMember", on_delete=models.SET_NULL, null=True, blank=True, related_name="entered_exam_marks"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("exam_schedule", "student")
        indexes = [
            models.Index(fields=["student", "-created_at"], name="exammark_student_idx"),
        ]

    def __str__(self):
        return f"{self.student} - {self.exam_schedule} - {self.marks_obtained}"

    @property
    def effective_marks(self):
        """Marks that count: obtained plus grace, capped at the maximum. None when not marked or not sat."""
        if self.marks_obtained is None or self.attendance != self.Attendance.PRESENT:
            return None
        total = self.marks_obtained + (self.grace_marks or 0)
        return min(total, self.exam_schedule.max_marks)


class ExamMarkChange(models.Model):
    """Append-only history of one mark: every first entry and every change, with who, when and why."""

    class Kind(models.TextChoices):
        ENTRY = "entry", "Entered"
        CORRECTION = "correction", "Corrected"
        IMPORT = "import", "Imported"
        GRACE = "grace", "Grace marks"
        RECHECK = "recheck", "Recheck"
        MODERATION = "moderation", "Moderation"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    mark = models.ForeignKey(ExamMark, on_delete=models.CASCADE, related_name="changes")
    kind = models.CharField(max_length=12, choices=Kind.choices)
    old_marks = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    new_marks = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    old_attendance = models.CharField(max_length=12, blank=True)
    new_attendance = models.CharField(max_length=12, blank=True)
    old_grace = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    new_grace = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    reason = models.CharField(max_length=500, blank=True)
    changed_by_user_id = models.UUIDField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["mark", "-created_at"], name="exammarkchange_mark_idx")]


class RecheckRequest(models.Model):
    """A request to re-check one published mark. Someone with manage_marks accepts (with the revised marks)
    or rejects it; accepting updates the mark and that student's published result, both on record."""

    class Status(models.TextChoices):
        PENDING = "pending", "Waiting"
        ACCEPTED = "accepted", "Accepted"
        REJECTED = "rejected", "Rejected"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    mark = models.ForeignKey(ExamMark, on_delete=models.CASCADE, related_name="rechecks")
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    reason = models.CharField(max_length=1000)
    original_marks = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    revised_marks = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    decision_comment = models.CharField(max_length=1000, blank=True)
    requested_by_user_id = models.UUIDField(null=True, blank=True)
    decided_by_user_id = models.UUIDField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    decided_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["mark"], condition=models.Q(status="pending"), name="exam_recheck_one_pending_per_mark"
            ),
        ]


class ExamComponentMark(models.Model):
    """
    Component-level score for one student mark record (e.g. Theory 65/80, Practical 18/20).
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    mark = models.ForeignKey(
        ExamMark, on_delete=models.CASCADE, related_name="component_marks"
    )
    component = models.ForeignKey(
        ExamScheduleComponent, on_delete=models.CASCADE, related_name="student_marks"
    )
    marks_obtained = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    is_absent = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("mark", "component")
        ordering = ["component__order", "component__name"]

    def __str__(self):
        return f"{self.mark.student} - {self.component.name}: {self.marks_obtained}"

    def clean(self):
        if self.marks_obtained is not None and self.component_id:
            if self.marks_obtained < 0:
                raise ValidationError({"marks_obtained": "Marks cannot be negative."})
            if self.marks_obtained > self.component.max_marks:
                raise ValidationError(
                    {"marks_obtained": f"Marks cannot exceed maximum component marks ({self.component.max_marks})."}
                )


class ExamResult(models.Model):
    """
    Immutable publication snapshot. Created ONCE, atomically, when an
    Examination is published - never recalculated afterward, even if
    GradeBoundary or ExamMark data changes later. subject_breakdown carries
    enough per-subject detail (marks/max/percentage/grade/absence) that
    rendering a student's published result never needs to re-derive
    anything from mutable configuration.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    examination = models.ForeignKey(Examination, on_delete=models.CASCADE, related_name="results")
    student = models.ForeignKey(
        "students.Student", on_delete=models.CASCADE, related_name="exam_results"
    )
    academic_year = models.CharField(max_length=20)
    academic_year_ref = models.ForeignKey(
        "academics.AcademicYear",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
    )

    total_marks_obtained = models.DecimalField(max_digits=8, decimal_places=2)
    total_max_marks = models.DecimalField(max_digits=8, decimal_places=2)
    percentage = models.DecimalField(max_digits=5, decimal_places=2)
    overall_grade = models.CharField(max_length=20, blank=True)
    is_pass = models.BooleanField()

    subject_breakdown = models.JSONField(default=list)

    published_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("examination", "student")
        ordering = ["-published_at"]

    def __str__(self):
        return f"{self.student} - {self.examination} - {self.percentage}%"


class GradeBoundary(models.Model):
    """
    Tenant-configurable grading scale (e.g. 90-100 -> A+). Deliberately not
    hardcoded - grading scales vary by school/country. Overlap/ordering is
    validated at the application layer (clean()/save()), not via a
    PostgreSQL EXCLUDE constraint, which would be excessive for a small,
    admin-managed table.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    academic_year = models.CharField(max_length=20)
    academic_year_ref = models.ForeignKey(
        "academics.AcademicYear",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
    )
    min_percentage = models.DecimalField(max_digits=5, decimal_places=2)
    max_percentage = models.DecimalField(max_digits=5, decimal_places=2)
    grade_label = models.CharField(max_length=20)
    grade_point = models.DecimalField(max_digits=4, decimal_places=2, null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["academic_year", "-min_percentage"]
        verbose_name_plural = "Grade Boundaries"

    def clean(self):
        if self.min_percentage is None or self.max_percentage is None:
            return
        if self.min_percentage < 0 or self.max_percentage > 100:
            raise ValidationError("Percentage values must be between 0 and 100.")
        if self.min_percentage >= self.max_percentage:
            raise ValidationError({"min_percentage": "min_percentage must be less than max_percentage."})

        overlapping = GradeBoundary.objects.filter(
            academic_year=self.academic_year,
            min_percentage__lt=self.max_percentage,
            max_percentage__gt=self.min_percentage,
        ).exclude(id=self.id)
        if overlapping.exists():
            raise ValidationError(
                f"This range overlaps with an existing grade boundary "
                f"({overlapping.first().grade_label}) for {self.academic_year}."
            )

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.grade_label} ({self.min_percentage}-{self.max_percentage}%, {self.academic_year})"


class ExaminationSettings(models.Model):
    """The school's examination rules: exactly one row per school. Reading never writes: with no row, ``load()``
    returns the defaults. Two-person publishing is off by default, so nothing changes until a school turns it on."""

    EDITABLE_FIELDS = ("require_separate_publisher", "show_rank_to_families")

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    singleton = models.BooleanField(default=True, unique=True, editable=False)
    # When on, one person requests publication of an examination's results and a different person publishes them.
    require_separate_publisher = models.BooleanField(default=False)
    # When on, a student's section rank is shown on the report card that students and parents see. Off by default:
    # many schools do not publish ranks to families.
    show_rank_to_families = models.BooleanField(default=False)
    updated_by_user_id = models.UUIDField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "Examination settings"
        constraints = [models.CheckConstraint(condition=models.Q(singleton=True), name="exam_settings_singleton_true")]

    @classmethod
    def load(cls):
        return cls.objects.filter(singleton=True).first() or cls()


class TermWeightage(models.Model):
    """
    Configurable term weightage per academic year and class level.
    Used to consolidate multi-term examinations into a final composite academic score
    (e.g., Periodic Test 10% + Mid-Term 30% + Final 60% = 100%).
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    academic_year = models.CharField(max_length=20)
    academic_year_ref = models.ForeignKey(
        "academics.AcademicYear",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
    )
    level = models.ForeignKey(
        "academics.AcademicLevel", on_delete=models.CASCADE, related_name="term_weightages"
    )
    examination = models.ForeignKey(
        Examination, on_delete=models.CASCADE, related_name="term_weightages"
    )
    weightage_percentage = models.DecimalField(max_digits=5, decimal_places=2)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("academic_year", "level", "examination")
        ordering = ["examination__start_date", "examination__name"]

    def __str__(self):
        return f"{self.level.name} - {self.examination.name} ({self.weightage_percentage}%) [{self.academic_year}]"

    def clean(self):
        if self.weightage_percentage is not None:
            if self.weightage_percentage <= 0 or self.weightage_percentage > 100:
                raise ValidationError({"weightage_percentage": "Weightage percentage must be between 0 and 100."})


class CoScholasticActivity(models.Model):
    """
    Co-scholastic domains prescribed by boards/schools
    (e.g., Art Education, Work Education, Health & Physical Education, Discipline).
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, unique=True)
    code = models.CharField(max_length=30, blank=True, default="")
    description = models.CharField(max_length=255, blank=True, default="")
    order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["order", "name"]
        verbose_name_plural = "Co-scholastic activities"

    def __str__(self):
        return self.name


class CoScholasticGrade(models.Model):
    """
    Direct letter grade awarded to a student in a co-scholastic activity for an examination.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    student = models.ForeignKey(
        "students.Student", on_delete=models.CASCADE, related_name="co_scholastic_grades"
    )
    examination = models.ForeignKey(
        Examination, on_delete=models.CASCADE, related_name="co_scholastic_grades"
    )
    activity = models.ForeignKey(
        CoScholasticActivity, on_delete=models.CASCADE, related_name="grades"
    )
    grade = models.CharField(max_length=10)
    remarks = models.CharField(max_length=255, blank=True, default="")
    recorded_by = models.ForeignKey(
        "staff.StaffMember",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="recorded_co_scholastic_grades",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("student", "examination", "activity")
        ordering = ["activity__order", "activity__name"]

    def __str__(self):
        return f"{self.student} - {self.activity.name}: {self.grade} ({self.examination.name})"


class ExamSitting(models.Model):
    """All the papers of one examination that start at the same date and time. Rooms and invigilators are
    allocated per sitting. Rows are created and kept in step with the schedules by allocation.sync_sittings."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    examination = models.ForeignKey(Examination, on_delete=models.CASCADE, related_name="sittings")
    date = models.DateField()
    start_time = models.TimeField()
    end_time = models.TimeField()

    class Meta:
        ordering = ["date", "start_time"]
        constraints = [
            models.UniqueConstraint(fields=["examination", "date", "start_time"], name="uniq_exam_sitting_slot"),
        ]

    def __str__(self):
        return f"{self.examination} {self.date} {self.start_time:%H:%M}"


class ExamSeat(models.Model):
    """One student's seat for a sitting, for the paper they are sitting there."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    sitting = models.ForeignKey(ExamSitting, on_delete=models.CASCADE, related_name="seats")
    room = models.ForeignKey("timetable.Room", on_delete=models.PROTECT, related_name="exam_seats")
    student = models.ForeignKey("students.Student", on_delete=models.CASCADE, related_name="exam_seats")
    schedule = models.ForeignKey(ExamSchedule, on_delete=models.CASCADE, related_name="seats")
    seat_number = models.PositiveIntegerField()

    # Who sat the paper, as the invigilator recorded it in the hall. Blank until marked.
    class HallStatus(models.TextChoices):
        PRESENT = "present", "Present"
        ABSENT = "absent", "Absent"

    hall_status = models.CharField(max_length=10, choices=HallStatus.choices, blank=True, default="")
    hall_marked_by_user_id = models.UUIDField(null=True, blank=True)
    hall_marked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["room__name", "seat_number"]
        constraints = [
            models.UniqueConstraint(fields=["sitting", "student"], name="uniq_exam_seat_student"),
            models.UniqueConstraint(fields=["sitting", "room", "seat_number"], name="uniq_exam_seat_position"),
        ]


class ExamInvigilation(models.Model):
    """A staff member's duty in a room for a sitting."""

    class Role(models.TextChoices):
        CHIEF = "chief", "Chief invigilator"
        INVIGILATOR = "invigilator", "Invigilator"
        RELIEF = "relief", "Relief"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    sitting = models.ForeignKey(ExamSitting, on_delete=models.CASCADE, related_name="invigilations")
    room = models.ForeignKey("timetable.Room", on_delete=models.PROTECT, related_name="exam_invigilations")
    # PROTECT: a staff record that has an exam duty on file is part of the exam record.
    staff = models.ForeignKey("staff.StaffMember", on_delete=models.PROTECT, related_name="exam_invigilations")
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.INVIGILATOR)
    created_by_id = models.UUIDField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["room__name", "role"]
        constraints = [
            models.UniqueConstraint(fields=["sitting", "staff"], name="uniq_exam_duty_staff_per_sitting"),
        ]


class MalpracticeCase(models.Model):
    """A report that a student cheated, and what the school decided. One case per student per paper. Reporting does
    not change the student's marks: they change only when the decision cancels them."""

    class Status(models.TextChoices):
        REPORTED = "reported", "Reported"
        DECIDED = "decided", "Decided"

    class Decision(models.TextChoices):
        DISMISSED = "dismissed", "Dismissed, no action"
        WARNING = "warning", "Warning, marks stand"
        MARKS_CANCELLED = "marks_cancelled", "This paper's marks cancelled"
        ALL_PAPERS_CANCELLED = "all_papers_cancelled", "All papers in this examination cancelled"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    examination = models.ForeignKey(Examination, on_delete=models.CASCADE, related_name="malpractice_cases")
    schedule = models.ForeignKey(ExamSchedule, on_delete=models.CASCADE, related_name="malpractice_cases")
    student = models.ForeignKey("students.Student", on_delete=models.CASCADE, related_name="malpractice_cases")

    description = models.TextField(help_text="What happened")
    evidence_notes = models.TextField(blank=True, help_text="What was found: items, witnesses, answer-sheet notes")
    reported_by_user_id = models.UUIDField(null=True, blank=True)
    reported_by_name = models.CharField(max_length=150, blank=True)

    status = models.CharField(max_length=10, choices=Status.choices, default=Status.REPORTED, db_index=True)
    decision = models.CharField(max_length=20, choices=Decision.choices, blank=True)
    decision_notes = models.TextField(blank=True)
    decided_by_user_id = models.UUIDField(null=True, blank=True)
    decided_by_name = models.CharField(max_length=150, blank=True)
    decided_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["schedule", "student"], name="uniq_malpractice_case_per_paper"),
        ]
