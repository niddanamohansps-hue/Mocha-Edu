"""Question bank (Stage Q1 and Q2): reusable questions written by subject teachers and approved by subject
reviewers, organised by chapter and topic.

A question belongs to a ``academics.Subject``, which already belongs to one class (``AcademicLevel``), so
"class and subject" is a single link. Questions are independent of any examination: an approved question can
be used in many papers later. Every content change is kept as a ``QuestionVersion``, and every review decision
as a ``QuestionReview``, so nothing about a question's history is ever overwritten.

Answers, explanations and marking schemes are staff-only data: students and parents have no access to this app.
"""
import uuid
from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q


class Chapter(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    subject = models.ForeignKey("academics.Subject", on_delete=models.CASCADE, related_name="chapters")
    name = models.CharField(max_length=150)
    order = models.PositiveSmallIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["subject", "order", "name"]
        constraints = [models.UniqueConstraint(fields=["subject", "name"], name="qb_chapter_unique_name")]

    def __str__(self):
        return self.name


class Topic(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    chapter = models.ForeignKey(Chapter, on_delete=models.CASCADE, related_name="topics")
    name = models.CharField(max_length=150)
    order = models.PositiveSmallIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["chapter", "order", "name"]
        constraints = [models.UniqueConstraint(fields=["chapter", "name"], name="qb_topic_unique_name")]

    def __str__(self):
        return self.name


class SubjectReviewer(models.Model):
    """A staff member named by the school to review the questions of one subject."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    subject = models.ForeignKey("academics.Subject", on_delete=models.CASCADE, related_name="question_reviewers")
    staff = models.ForeignKey("staff.StaffMember", on_delete=models.CASCADE, related_name="question_review_subjects")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["subject", "staff"]
        constraints = [models.UniqueConstraint(fields=["subject", "staff"], name="qb_reviewer_unique")]

    def __str__(self):
        return f"{self.staff} reviews {self.subject}"


class Question(models.Model):
    class Type(models.TextChoices):
        MCQ = "mcq", "Multiple choice (one answer)"
        MULTI_SELECT = "multi_select", "Multiple choice (several answers)"
        TRUE_FALSE = "true_false", "True or false"
        SHORT = "short", "Short answer"
        LONG = "long", "Long answer"
        CASE_BASED = "case_based", "Case-based"

    class Difficulty(models.TextChoices):
        EASY = "easy", "Easy"
        MEDIUM = "medium", "Medium"
        HARD = "hard", "Hard"

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        SUBMITTED = "submitted", "Waiting for review"
        CHANGES_REQUESTED = "changes_requested", "Changes requested"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"
        ARCHIVED = "archived", "Archived"

    CHOICE_TYPES = (Type.MCQ, Type.MULTI_SELECT, Type.TRUE_FALSE)
    EDITABLE_STATUSES = (Status.DRAFT, Status.CHANGES_REQUESTED)
    # The content a version records and a duplicate check compares.
    CONTENT_FIELDS = (
        "question_type", "difficulty", "marks", "body", "options", "answer", "explanation", "marking_scheme",
        "learning_outcome", "chapter_id", "topic_id",
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    subject = models.ForeignKey("academics.Subject", on_delete=models.PROTECT, related_name="questions")
    chapter = models.ForeignKey(Chapter, null=True, blank=True, on_delete=models.PROTECT, related_name="questions")
    topic = models.ForeignKey(Topic, null=True, blank=True, on_delete=models.PROTECT, related_name="questions")
    question_type = models.CharField(max_length=20, choices=Type.choices)
    difficulty = models.CharField(max_length=10, choices=Difficulty.choices, default=Difficulty.MEDIUM)
    marks = models.DecimalField(max_digits=5, decimal_places=2, validators=[MinValueValidator(Decimal("0.5"))])
    body = models.TextField()
    # For choice questions: [{"text": "...", "is_correct": true}, ...]. Empty for written answers.
    options = models.JSONField(default=list, blank=True)
    answer = models.TextField(blank=True, help_text="The expected or model answer.")
    explanation = models.TextField(blank=True)
    marking_scheme = models.TextField(blank=True, help_text="How marks are given, for written answers.")
    learning_outcome = models.CharField(max_length=255, blank=True)

    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    version = models.PositiveIntegerField(default=1)
    # sha256 of the normalised body, per subject: finds the same question typed twice.
    content_hash = models.CharField(max_length=64, db_index=True)

    author = models.ForeignKey("staff.StaffMember", null=True, blank=True, on_delete=models.SET_NULL, related_name="authored_questions")
    created_by_user_id = models.UUIDField()
    submitted_at = models.DateTimeField(null=True, blank=True)
    decided_at = models.DateTimeField(null=True, blank=True)
    decided_by_user_id = models.UUIDField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]
        indexes = [
            models.Index(fields=["subject", "status"], name="qb_question_subject_status"),
            models.Index(fields=["created_by_user_id", "status"], name="qb_question_author_status"),
        ]
        constraints = [
            models.CheckConstraint(condition=Q(marks__gt=0), name="qb_question_marks_positive"),
            models.CheckConstraint(condition=Q(version__gte=1), name="qb_question_version_positive"),
        ]

    def __str__(self):
        return self.body[:60]


class QuestionVersion(models.Model):
    """The full content of a question as it was saved. Never changed or deleted."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name="versions")
    number = models.PositiveIntegerField()
    content = models.JSONField()
    created_by_user_id = models.UUIDField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["question", "-number"]
        constraints = [models.UniqueConstraint(fields=["question", "number"], name="qb_version_unique_number")]


class QuestionReview(models.Model):
    """One review decision on one version of a question."""

    class Decision(models.TextChoices):
        APPROVED = "approved", "Approved"
        CHANGES_REQUESTED = "changes_requested", "Changes requested"
        REJECTED = "rejected", "Rejected"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name="reviews")
    version = models.PositiveIntegerField()
    decision = models.CharField(max_length=20, choices=Decision.choices)
    comment = models.TextField(blank=True)
    reviewer = models.ForeignKey("staff.StaffMember", null=True, blank=True, on_delete=models.SET_NULL, related_name="question_reviews")
    reviewer_user_id = models.UUIDField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["question", "-created_at"]
