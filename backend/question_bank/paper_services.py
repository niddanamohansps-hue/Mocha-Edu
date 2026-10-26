"""Question paper rules (Stages Q3 and Q4): blueprint, assembly, approval, freezing and release.

Who:
  * ``prepare_papers`` (an examination controller): create a paper, set its blueprint, add questions or fill it
    from the blueprint, submit it. Edits are allowed only while the paper is a draft.
  * ``approve_papers`` (the principal, say): approve or send back a submitted paper, release it, withdraw it.
    The approver is never the person who prepared it.
  * Teachers of the subject: open a released paper and its answer key (to print and to mark). Nothing earlier.
  * Students and parents: never.
The owner can do everything except approve a paper they prepared.

A paper uses approved questions of its own subject only. Unless the paper allows it, a question used in one set
(A) cannot also be in another live set (B) of the same exam and subject. On approval every question's content is
copied into the paper, so the approved paper never changes afterwards. Every opening of a paper or answer key is
logged. Every change locks the paper row, so two people cannot approve, release or edit it at once.
"""
import random
from decimal import Decimal

from django.db import transaction
from django.db.models import Q, Sum
from django.utils import timezone
from rest_framework import serializers

from .models import PaperAccessLog, PaperQuestion, Question, QuestionPaper
from .services import has_perm, is_owner, staff_for

Status = QuestionPaper.Status
LIVE = (Status.DRAFT, Status.SUBMITTED, Status.APPROVED, Status.RELEASED)


def _marks(value):
    """10.00 -> "10", 80.50 -> "80.5"."""
    return f"{Decimal(value).normalize():f}"


# --- Who may do what ----------------------------------------------------------------------------------------

def can_prepare(request):
    return is_owner(request.user) or has_perm(request, "prepare_papers")


def can_approve(request):
    return is_owner(request.user) or has_perm(request, "approve_papers")


def is_released(paper, now=None):
    """Released, or approved with a release time that has passed."""
    if paper.status == Status.RELEASED:
        return True
    return paper.status == Status.APPROVED and paper.release_at is not None and paper.release_at <= (now or timezone.now())


def taught_subject_ids(request):
    staff = staff_for(request.user)
    instructor = getattr(staff, "instructor_record", None) if staff else None
    if instructor is None:
        return set()
    from academics.models import SubjectAssignment

    return set(SubjectAssignment.objects.filter(instructor=instructor).values_list("subject_id", flat=True))


def visible_papers(request):
    """The exam office sees every paper; a teacher sees released papers of subjects they teach; nobody else any."""
    qs = QuestionPaper.objects.select_related("examination", "subject__level")
    if can_prepare(request) or can_approve(request):
        return qs
    subjects = taught_subject_ids(request)
    if not subjects:
        return qs.none()
    now = timezone.now()
    return qs.filter(subject_id__in=subjects).filter(
        Q(status=Status.RELEASED) | Q(status=Status.APPROVED, release_at__isnull=False, release_at__lte=now)
    )


def may_open_content(request, paper):
    """The printable paper and the answer key: the exam office at any stage, a subject teacher once released."""
    if can_prepare(request) or can_approve(request):
        return True
    return is_released(paper) and paper.subject_id in taught_subject_ids(request)


# --- Shared checks ------------------------------------------------------------------------------------------------

def _locked(paper):
    return QuestionPaper.objects.select_for_update(of=("self",)).select_related("subject", "examination").get(pk=paper.pk)


def _require_status(paper, allowed, verb):
    if paper.status not in allowed:
        raise serializers.ValidationError({"paper": f"A paper that is {paper.get_status_display().lower()} cannot be {verb}."})


def _require_draft(paper):
    _require_status(paper, QuestionPaper.EDITABLE, "changed")


def scheduled_max_marks(examination, subject):
    """The maximum marks the exam schedule gives this subject, or None when no schedule exists yet."""
    from examinations.models import ExamSchedule

    values = set(ExamSchedule.objects.filter(examination=examination, subject=subject).values_list("max_marks", flat=True))
    if len(values) > 1:
        raise serializers.ValidationError(
            {"total_marks": "The exam schedule gives this subject different maximum marks in different sections. Make them the same first."}
        )
    return values.pop() if values else None


def check_paper_fields(*, examination, subject, total_marks):
    if examination.is_published:
        raise serializers.ValidationError({"examination": "The results of this examination are already published."})
    if subject.level_id is None:
        raise serializers.ValidationError({"subject": "Choose a subject of a class."})
    expected = scheduled_max_marks(examination, subject)
    if expected is not None and Decimal(total_marks) != expected:
        raise serializers.ValidationError(
            {"total_marks": f"The exam schedule gives this subject {_marks(expected)} marks, so the paper must total {_marks(expected)}."}
        )


def _sibling_question_ids(paper):
    """Questions already in another live set of the same exam and subject."""
    return set(
        PaperQuestion.objects.filter(
            paper__examination_id=paper.examination_id, paper__subject_id=paper.subject_id, paper__status__in=LIVE,
        ).exclude(paper_id=paper.id).values_list("question_id", flat=True)
    )


def eligible_questions(paper):
    """Approved questions of the paper's subject that are not already in it (nor, unless allowed, in another set)."""
    qs = Question.objects.filter(subject_id=paper.subject_id, status=Question.Status.APPROVED).exclude(paper_items__paper=paper)
    if not paper.allow_shared_questions:
        qs = qs.exclude(id__in=_sibling_question_ids(paper))
    return qs


def _matches(rule, question):
    return (
        (not rule.question_type or question.question_type == rule.question_type)
        and (not rule.difficulty or question.difficulty == rule.difficulty)
        and (rule.chapter_id is None or question.chapter_id == rule.chapter_id)
    )


def _specificity(rule):
    return -(bool(rule.question_type) + bool(rule.difficulty) + (rule.chapter_id is not None))


def unmet_rules(section, items=None):
    """Each rule's shortfall in a section, matching every question to at most one rule, most specific rule first."""
    items = list(items if items is not None else section.items.select_related("question"))
    free = list(items)
    shortfall = []
    for rule in sorted(section.rules.all(), key=_specificity):
        matched = [i for i in free if _matches(rule, i.question)][: rule.count]
        for item in matched:
            free.remove(item)
        if len(matched) < rule.count:
            shortfall.append((rule, rule.count - len(matched)))
    return shortfall


def describe_rule(rule):
    parts = [rule.get_difficulty_display().lower() if rule.difficulty else "", rule.get_question_type_display().lower() if rule.question_type else "question"]
    text = " ".join(p for p in parts if p)
    if rule.chapter_id:
        text += f" from {rule.chapter.name}"
    return text


def problems(paper):
    """Everything that stops this paper being submitted or approved, as plain sentences. Empty means it is ready."""
    found = []
    items = list(paper.items.select_related("question", "section"))
    if not items:
        return ["The paper has no questions."]
    total = sum((i.marks for i in items), Decimal("0"))
    if total != paper.total_marks:
        found.append(f"The questions add up to {_marks(total)} marks; the paper is for {_marks(paper.total_marks)}.")
    for item in items:
        if item.question.status != Question.Status.APPROVED:
            found.append(f"A question in {item.section.title} is no longer approved ({item.question.get_status_display().lower()}). Remove it.")
    for section in paper.sections.prefetch_related("rules__chapter"):
        in_section = [i for i in items if i.section_id == section.id]
        rules = list(section.rules.all())
        if rules:
            needed = sum(r.count for r in rules)
            if len(in_section) != needed:
                found.append(f"{section.title} has {len(in_section)} questions; its blueprint asks for {needed}.")
            for rule, short in unmet_rules(section, in_section):
                found.append(f"{section.title} needs {short} more {describe_rule(rule)}.")
        elif not in_section:
            found.append(f"{section.title} has no questions.")
    if not paper.allow_shared_questions:
        shared = _sibling_question_ids(paper) & {i.question_id for i in items}
        if shared:
            found.append(f"{len(shared)} question(s) are also in another set of this paper.")
    try:
        expected = scheduled_max_marks(paper.examination, paper.subject)
    except serializers.ValidationError as exc:
        found.append(str(exc.detail["total_marks"]))
    else:
        if expected is not None and expected != paper.total_marks:
            found.append(f"The exam schedule now gives this subject {_marks(expected)} marks; change the paper's total to match.")
    return found


# --- Building a draft ---------------------------------------------------------------------------------------------

def add_question(*, paper, section, question):
    with transaction.atomic():
        paper = _locked(paper)
        _require_draft(paper)
        if section.paper_id != paper.id:
            raise serializers.ValidationError({"section": "That section belongs to another paper."})
        question = Question.objects.select_for_update().get(pk=question.pk)
        if question.subject_id != paper.subject_id:
            raise serializers.ValidationError({"question": "That question is for another subject."})
        if question.status != Question.Status.APPROVED:
            raise serializers.ValidationError({"question": "Only approved questions can go in a paper."})
        if paper.items.filter(question=question).exists():
            raise serializers.ValidationError({"question": "This question is already in the paper."})
        if not paper.allow_shared_questions and question.id in _sibling_question_ids(paper):
            raise serializers.ValidationError({"question": "This question is already in another set of this paper."})
        order = (section.items.order_by("-order").values_list("order", flat=True).first() or 0) + 1
        return PaperQuestion.objects.create(
            paper=paper, section=section, question=question, question_version=question.version, order=order, marks=question.marks,
        )


def remove_question(*, item):
    with transaction.atomic():
        paper = _locked(item.paper)
        _require_draft(paper)
        item.delete()


def autofill(*, paper, section=None, seed=None):
    """Fill one section, or every section with a blueprint, from its rules: the section's questions are replaced
    by a random choice of eligible questions. All or nothing: if any rule cannot be met, nothing changes and the
    shortfall is reported."""
    rng = random.Random(seed)
    with transaction.atomic():
        paper = _locked(paper)
        _require_draft(paper)
        sections = [section] if section is not None else list(paper.sections.all())
        if section is not None and section.paper_id != paper.id:
            raise serializers.ValidationError({"section": "That section belongs to another paper."})
        targets = [s for s in sections if s.rules.exists()]
        if not targets:
            raise serializers.ValidationError({"section": "Add blueprint rules to the section first."})
        PaperQuestion.objects.filter(paper=paper, section__in=targets).delete()
        pool = list(eligible_questions(paper).select_related("chapter"))
        rng.shuffle(pool)
        used, shortfall, chosen = set(), [], []
        for target in targets:
            for rule in sorted(target.rules.select_related("chapter"), key=_specificity):
                picks = [q for q in pool if q.id not in used and _matches(rule, q)][: rule.count]
                used.update(q.id for q in picks)
                chosen.extend((target, q) for q in picks)
                if len(picks) < rule.count:
                    shortfall.append(f"{target.title}: only {len(picks)} of {rule.count} {describe_rule(rule)} are available.")
        if shortfall:
            transaction.set_rollback(True)
            raise serializers.ValidationError({"blueprint": shortfall})
        order = {}
        rows = []
        for target, question in chosen:
            order[target.id] = order.get(target.id, 0) + 1
            rows.append(PaperQuestion(paper=paper, section=target, question=question, question_version=question.version,
                                      order=order[target.id], marks=question.marks))
        PaperQuestion.objects.bulk_create(rows)
    return len(rows)


# --- Approval and release -----------------------------------------------------------------------------------------

def submit(*, request, paper):
    with transaction.atomic():
        paper = _locked(paper)
        _require_status(paper, (Status.DRAFT,), "submitted")
        found = problems(paper)
        if found:
            raise serializers.ValidationError({"paper": found})
        paper.status, paper.submitted_at, paper.review_comment = Status.SUBMITTED, timezone.now(), ""
        paper.save(update_fields=["status", "submitted_at", "review_comment", "updated_at"])
    return paper


def send_back(*, request, paper, comment):
    comment = (comment or "").strip()
    if not comment:
        raise serializers.ValidationError({"comment": "Tell the preparer what to change."})
    with transaction.atomic():
        paper = _locked(paper)
        _require_status(paper, (Status.SUBMITTED,), "sent back")
        paper.status, paper.review_comment = Status.DRAFT, comment[:2000]
        paper.save(update_fields=["status", "review_comment", "updated_at"])
    return paper


def freeze(paper):
    """The full, final content of the paper: what is printed, and what the answer key shows."""
    sections = []
    for section in paper.sections.all():
        items = section.items.select_related("question__chapter", "question__topic")
        sections.append({
            "title": section.title, "instructions": section.instructions,
            "questions": [{
                "number": index, "marks": str(item.marks), "question_id": str(item.question_id), "version": item.question_version,
                "type": item.question.question_type, "difficulty": item.question.difficulty, "body": item.question.body,
                "options": [o["text"] for o in item.question.options],
                "correct": [i for i, o in enumerate(item.question.options) if o["is_correct"]],
                "answer": item.question.answer, "explanation": item.question.explanation,
                "marking_scheme": item.question.marking_scheme,
                "chapter": item.question.chapter.name if item.question.chapter_id else "",
            } for index, item in enumerate(items, start=1)],
        })
    return {
        "title": paper.title, "set_label": paper.set_label, "instructions": paper.instructions,
        "examination": paper.examination.name, "subject": paper.subject.name, "level": paper.subject.level.name,
        "total_marks": str(paper.total_marks), "duration_minutes": paper.duration_minutes, "sections": sections,
    }


def approve(*, request, paper):
    with transaction.atomic():
        paper = _locked(paper)
        _require_status(paper, (Status.SUBMITTED,), "approved")
        if paper.prepared_by_user_id == request.user.id:
            raise serializers.ValidationError({"paper": "Someone other than the person who prepared this paper must approve it."})
        found = problems(paper)
        if found:
            raise serializers.ValidationError({"paper": found})
        # Lock the questions too, so none can be archived while the paper is frozen.
        list(Question.objects.select_for_update().filter(paper_items__paper=paper))
        paper.frozen_content = freeze(paper)
        paper.status, paper.approved_by_user_id, paper.approved_at = Status.APPROVED, request.user.id, timezone.now()
        paper.save(update_fields=["frozen_content", "status", "approved_by_user_id", "approved_at", "updated_at"])
    return paper


def schedule_release(*, paper, release_at):
    with transaction.atomic():
        paper = _locked(paper)
        _require_status(paper, (Status.DRAFT, Status.SUBMITTED, Status.APPROVED), "scheduled")
        if release_at is not None and release_at <= timezone.now():
            raise serializers.ValidationError({"release_at": "Choose a time in the future, or release the paper now."})
        paper.release_at = release_at
        paper.save(update_fields=["release_at", "updated_at"])
    return paper


def release(*, paper):
    with transaction.atomic():
        paper = _locked(paper)
        _require_status(paper, (Status.APPROVED,), "released")
        paper.status, paper.released_at = Status.RELEASED, timezone.now()
        paper.save(update_fields=["status", "released_at", "updated_at"])
    return paper


def withdraw(*, paper, reason):
    reason = (reason or "").strip()
    if not reason:
        raise serializers.ValidationError({"reason": "Give the reason, for example a suspected leak."})
    with transaction.atomic():
        paper = _locked(paper)
        _require_status(paper, (Status.APPROVED, Status.RELEASED), "withdrawn")
        paper.status, paper.withdraw_reason, paper.withdrawn_at = Status.WITHDRAWN, reason[:255], timezone.now()
        paper.save(update_fields=["status", "withdraw_reason", "withdrawn_at", "updated_at"])
    return paper


def log_access(request, paper, kind):
    PaperAccessLog.objects.create(paper=paper, user_id=request.user.id, kind=kind, status_at_access=paper.status)


def content_for(paper):
    """The approved content once frozen; the live content of a draft or submitted paper (for its preparers)."""
    return paper.frozen_content or freeze(paper)


def paper_marks(paper):
    return paper.items.aggregate(total=Sum("marks"))["total"] or Decimal("0")

