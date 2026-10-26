"""Question bank rules: who may write and review what, the content of each question type, and the review states.

Scope (decided per request, never by the screen):
  * Owner, or anyone with ``manage_question_bank``: every subject.
  * A teacher (an Instructor) with ``create_questions``: only subjects they teach (a ``SubjectAssignment`` in any
    section of that subject). A staff member who is not a teacher writes only with ``manage_question_bank``.
  * A reviewer with ``review_questions``: only subjects the school named them reviewer for (``SubjectReviewer``).
    Nobody reviews their own question, whatever their role.

States:  draft -> submitted -> approved | changes_requested | rejected
         changes_requested -> (edit) -> submitted again
         approved -> archived;  draft or rejected -> archived
Only a draft or a question with changes requested can be edited, and only by its author (or a manager). Each
change of content saves a new ``QuestionVersion``; each decision a ``QuestionReview``. Every state change locks
the question row, so two reviewers cannot decide at once and an edit cannot slip in during a review.
"""
import hashlib
import re
from decimal import Decimal

from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework import serializers

from .models import Question, QuestionReview, QuestionVersion, SubjectReviewer

Status = Question.Status
Type = Question.Type
MAX_OPTIONS = 8


# --- Who is asking -------------------------------------------------------------------------------------------

def staff_for(user):
    from attendance.services import get_staff_member_for_user

    return get_staff_member_for_user(user)


def is_owner(user):
    from roles.models import UserRole

    return bool(getattr(user, "is_superuser", False)) or UserRole.objects.filter(user=user, role__slug="owner").exists()


def has_perm(request, codename):
    from roles.permissions import HasPermission

    return HasPermission(codename).has_permission(request, None)


def is_manager(request):
    return is_owner(request.user) or has_perm(request, "manage_question_bank")


def authorable_subject_ids(request):
    """Subjects this person may write questions for, or None for every subject."""
    if is_manager(request):
        return None
    if not has_perm(request, "create_questions"):
        return set()
    staff = staff_for(request.user)
    instructor = getattr(staff, "instructor_record", None) if staff else None
    if instructor is None:
        return set()
    from academics.models import SubjectAssignment

    return set(SubjectAssignment.objects.filter(instructor=instructor).values_list("subject_id", flat=True))


def reviewable_subject_ids(request):
    """Subjects this person may review, or None for every subject (the owner)."""
    if is_owner(request.user):
        return None
    if not has_perm(request, "review_questions"):
        return set()
    staff = staff_for(request.user)
    if staff is None:
        return set()
    return set(SubjectReviewer.objects.filter(staff=staff).values_list("subject_id", flat=True))


def _in(subject_id, allowed):
    return allowed is None or subject_id in allowed


def visible_questions(request):
    """The questions this person may see: their own; approved ones of subjects they teach (or of every subject
    with ``view_question_bank``); and submitted or decided ones of subjects they review. A manager sees everything.
    Another person's draft is never visible except to a manager."""
    qs = Question.objects.select_related("subject__level", "chapter", "topic", "author__profile")
    if is_manager(request):  # the owner is always a manager
        return qs
    authorable = authorable_subject_ids(request)
    reviewable = reviewable_subject_ids(request)
    approved_here = Q(status=Status.APPROVED) if has_perm(request, "view_question_bank") else Q(subject_id__in=authorable, status=Status.APPROVED)
    return qs.filter(
        Q(created_by_user_id=request.user.id)
        | approved_here
        | (Q(subject_id__in=reviewable) & ~Q(status=Status.DRAFT))
    )


# --- Content ---------------------------------------------------------------------------------------------------

def normalise(text):
    return re.sub(r"\s+", " ", (text or "").strip().lower())


def content_hash(subject_id, body):
    return hashlib.sha256(f"{subject_id}|{normalise(body)}".encode("utf-8")).hexdigest()


def clean_options(question_type, options):
    """Check and tidy the choices of a choice question; written-answer types carry none."""
    if question_type not in Question.CHOICE_TYPES:
        if options:
            raise serializers.ValidationError({"options": "Only multiple-choice and true/false questions have options."})
        return []
    if question_type == Type.TRUE_FALSE and not options:
        raise serializers.ValidationError({"options": "Mark which of True or False is correct."})
    if not isinstance(options, list):
        raise serializers.ValidationError({"options": "Options must be a list."})
    cleaned = []
    for option in options:
        if not isinstance(option, dict) or not isinstance(option.get("text"), str) or not isinstance(option.get("is_correct"), bool):
            raise serializers.ValidationError({"options": "Each option needs a text and whether it is correct."})
        text = option["text"].strip()
        if not text:
            raise serializers.ValidationError({"options": "An option cannot be empty."})
        if len(text) > 500:
            raise serializers.ValidationError({"options": "Keep each option under 500 characters."})
        cleaned.append({"text": text, "is_correct": option["is_correct"]})
    if len({normalise(o["text"]) for o in cleaned}) != len(cleaned):
        raise serializers.ValidationError({"options": "Two options say the same thing."})
    correct = sum(o["is_correct"] for o in cleaned)
    if question_type == Type.TRUE_FALSE:
        if sorted(normalise(o["text"]) for o in cleaned) != ["false", "true"]:
            raise serializers.ValidationError({"options": "A true/false question has exactly the options True and False."})
        if correct != 1:
            raise serializers.ValidationError({"options": "Exactly one of True or False is correct."})
    elif not 2 <= len(cleaned) <= MAX_OPTIONS:
        raise serializers.ValidationError({"options": f"Give between 2 and {MAX_OPTIONS} options."})
    elif question_type == Type.MCQ and correct != 1:
        raise serializers.ValidationError({"options": "A single-answer question has exactly one correct option."})
    elif question_type == Type.MULTI_SELECT and correct < 1:
        raise serializers.ValidationError({"options": "Mark at least one correct option."})
    return cleaned


def check_content(data):
    """``data`` holds the full content after the change. Raises on anything incomplete or inconsistent."""
    body = (data.get("body") or "").strip()
    if not body:
        raise serializers.ValidationError({"body": "Write the question."})
    marks = data.get("marks")
    if marks is None or Decimal(marks) <= 0:
        raise serializers.ValidationError({"marks": "Marks must be more than 0."})
    if Decimal(marks) * 2 != int(Decimal(marks) * 2):
        raise serializers.ValidationError({"marks": "Marks go in steps of 0.5."})
    subject, chapter, topic = data["subject"], data.get("chapter"), data.get("topic")
    if chapter is not None and chapter.subject_id != subject.id:
        raise serializers.ValidationError({"chapter": "That chapter belongs to another subject."})
    if topic is not None:
        if chapter is None:
            raise serializers.ValidationError({"topic": "Choose the chapter first."})
        if topic.chapter_id != chapter.id:
            raise serializers.ValidationError({"topic": "That topic belongs to another chapter."})
    data["body"] = body
    data["options"] = clean_options(data["question_type"], data.get("options") or [])
    if data["question_type"] not in Question.CHOICE_TYPES and not (data.get("answer") or "").strip():
        raise serializers.ValidationError({"answer": "Give the expected answer, so a reviewer and a marker can check it."})
    return data


def _snapshot(question):
    content = {name: getattr(question, name) for name in Question.CONTENT_FIELDS}
    content["marks"] = str(content["marks"])
    for key in ("chapter_id", "topic_id"):
        content[key] = str(content[key]) if content[key] else None
    return content


def _save_version(question, user_id):
    QuestionVersion.objects.create(question=question, number=question.version, content=_snapshot(question), created_by_user_id=user_id)


def _duplicate_of(subject_id, body, exclude_id=None):
    qs = Question.objects.filter(content_hash=content_hash(subject_id, body)).exclude(status__in=[Status.ARCHIVED, Status.REJECTED])
    if exclude_id:
        qs = qs.exclude(pk=exclude_id)
    return qs.first()


def _refuse_duplicate(subject_id, body, exclude_id=None):
    twin = _duplicate_of(subject_id, body, exclude_id)
    if twin is not None:
        raise serializers.ValidationError(
            {"body": f"The same question already exists for this subject ({twin.get_status_display().lower()}). Reuse it instead."}
        )


# --- Writing ---------------------------------------------------------------------------------------------------

def create_question(*, request, data):
    if not _in(data["subject"].id, authorable_subject_ids(request)):
        raise serializers.ValidationError({"subject": "You can only write questions for subjects you teach."})
    data = check_content(dict(data))
    with transaction.atomic():
        _refuse_duplicate(data["subject"].id, data["body"])
        question = Question.objects.create(
            **{k: v for k, v in data.items() if k in ("subject", "chapter", "topic", "question_type", "difficulty", "marks",
                                                       "body", "options", "answer", "explanation", "marking_scheme", "learning_outcome")},
            content_hash=content_hash(data["subject"].id, data["body"]),
            author=staff_for(request.user), created_by_user_id=request.user.id,
        )
        _save_version(question, request.user.id)
    return question


def _locked(question):
    # Lock only the question row: chapter and topic are optional joins, and PostgreSQL cannot lock their side.
    return Question.objects.select_for_update(of=("self",)).select_related("subject", "chapter", "topic").get(pk=question.pk)


def _require_author_or_manager(request, question):
    if question.created_by_user_id != request.user.id and not is_manager(request):
        raise serializers.ValidationError({"question": "Only the author can change this question."})


def update_question(*, request, question, data):
    with transaction.atomic():
        question = _locked(question)
        _require_author_or_manager(request, question)
        if question.status not in Question.EDITABLE_STATUSES:
            raise serializers.ValidationError({"question": f"A question that is {question.get_status_display().lower()} cannot be edited."})
        if "subject" in data and data["subject"].id != question.subject_id:
            raise serializers.ValidationError({"subject": "A question cannot move to another subject. Write a new one there."})
        merged = {name: getattr(question, name) for name in ("subject", "chapter", "topic", "question_type", "difficulty", "marks",
                                                              "body", "options", "answer", "explanation", "marking_scheme", "learning_outcome")}
        merged.update(data)
        merged = check_content(merged)
        changed = [k for k in merged if k != "subject" and getattr(question, k) != merged[k]]
        if not changed:
            return question
        _refuse_duplicate(question.subject_id, merged["body"], exclude_id=question.pk)
        for key in changed:
            setattr(question, key, merged[key])
        question.content_hash = content_hash(question.subject_id, question.body)
        question.version += 1
        question.save()
        _save_version(question, request.user.id)
    return question


def delete_question(*, request, question):
    """Only a draft that was never submitted can be deleted; anything else is archived instead, to keep its history."""
    with transaction.atomic():
        question = _locked(question)
        _require_author_or_manager(request, question)
        if question.status != Status.DRAFT or question.submitted_at is not None:
            raise serializers.ValidationError({"question": "Only a draft that was never submitted can be deleted. Archive it instead."})
        question.delete()


# --- Review ------------------------------------------------------------------------------------------------------

def submit_question(*, request, question):
    with transaction.atomic():
        question = _locked(question)
        _require_author_or_manager(request, question)
        if question.status not in Question.EDITABLE_STATUSES:
            raise serializers.ValidationError({"question": f"A question that is {question.get_status_display().lower()} cannot be submitted."})
        question.status = Status.SUBMITTED
        question.submitted_at = timezone.now()
        question.save(update_fields=["status", "submitted_at", "updated_at"])
    return question


def review_question(*, request, question, decision, comment=""):
    comment = (comment or "").strip()
    if decision not in QuestionReview.Decision.values:
        raise serializers.ValidationError({"decision": "Choose approve, request changes or reject."})
    if decision != QuestionReview.Decision.APPROVED and not comment:
        raise serializers.ValidationError({"comment": "Tell the author what to change, or why it is rejected."})
    with transaction.atomic():
        question = _locked(question)
        if not _in(question.subject_id, reviewable_subject_ids(request)):
            raise serializers.ValidationError({"question": "You are not a reviewer for this subject."})
        if question.created_by_user_id == request.user.id:
            raise serializers.ValidationError({"question": "You cannot review your own question."})
        if question.status != Status.SUBMITTED:
            raise serializers.ValidationError({"question": "Only a question waiting for review can be reviewed."})
        QuestionReview.objects.create(
            question=question, version=question.version, decision=decision, comment=comment[:2000],
            reviewer=staff_for(request.user), reviewer_user_id=request.user.id,
        )
        question.status = decision
        question.decided_at, question.decided_by_user_id = timezone.now(), request.user.id
        question.save(update_fields=["status", "decided_at", "decided_by_user_id", "updated_at"])
    _notify_author(question, decision, comment)
    return question


def archive_question(*, request, question):
    with transaction.atomic():
        question = _locked(question)
        allowed = is_manager(request) or question.created_by_user_id == request.user.id or _in(question.subject_id, reviewable_subject_ids(request))
        if not allowed:
            raise serializers.ValidationError({"question": "You cannot archive this question."})
        if question.status in (Status.ARCHIVED, Status.SUBMITTED):
            raise serializers.ValidationError({"question": "A question waiting for review is decided first; an archived one stays archived."})
        question.status = Status.ARCHIVED
        question.save(update_fields=["status", "updated_at"])
    return question


def _notify_author(question, decision, comment):
    """An in-app notice for the author. A notice that fails never undoes the decision."""
    from notifications.services import notify

    if question.author_id is None or not question.author.profile.user_id:
        return
    words = {"approved": "approved", "changes_requested": "sent back for changes", "rejected": "rejected"}[decision]
    try:
        notify(
            recipient_user_id=question.author.profile.user_id, title=f"Your question was {words}",
            body=(f"{question.subject.name}: {question.body[:120]}" + (f" Reviewer: {comment[:200]}" if comment else ""))[:500],
            category="question_bank", link=f"/dashboard/question-bank/{question.id}",
        )
    except Exception:  # pragma: no cover - a notice is best effort
        pass


# --- Chapters and topics -------------------------------------------------------------------------------------------

def chapter_in_use(chapter):
    return Question.objects.filter(chapter=chapter).exists()


def topic_in_use(topic):
    return Question.objects.filter(topic=topic).exists()

