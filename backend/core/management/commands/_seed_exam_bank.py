"""The question_bank step of seed_connect_school: a working examination question workflow for the demo school.

  * Roles: Question Writer (the subject teachers), Question Reviewer (a senior teacher named reviewer of the
    subjects) and Examination Controller (prepares papers). The owner (principal) approves papers.
  * Chapters and topics for Class 10 Mathematics and Science, Class 8 Science and English.
  * Questions in every state: approved (some after a round of changes), waiting for review, sent back, rejected,
    draft and archived, with versions and review history.
  * Papers: the past Annual Examination's Class 10 Mathematics Set A (released, opened by staff) and Set B
    (approved, then withdrawn); an upcoming Class 10 Pre-Board Examination with Mathematics Set A approved and
    due for release on the morning of the exam, Set B waiting for approval, and a Science Set A still a draft.

Rows are written directly (there is no web request), but through the question bank's own content checks, version
and freeze helpers, so they look exactly as the screens would make them. Papers are filled and approved through
the paper services, so blueprint, marks and set rules are checked for real.
"""
import random
from datetime import date, datetime, time, timedelta
from types import SimpleNamespace
from zoneinfo import ZoneInfo

from . import _seed_questions as content

ZONE = ZoneInfo("Asia/Kolkata")

ROLES = {
    "qb-question-writer": ("Question Writer", ["create_questions", "view_examinations"]),
    "qb-question-reviewer": ("Question Reviewer", ["review_questions", "create_questions", "view_question_bank", "view_examinations"]),
    "qb-exam-controller": ("Examination Controller", ["prepare_papers", "view_question_bank", "manage_question_bank", "view_examinations"]),
}

CHANGE_COMMENTS = [
    "Please give the answer in its simplest form and show the working.",
    "The marking scheme should say how the 3 marks are split.",
    "Two options are almost the same. Make the distractors clearer.",
    "Mention the units in the question and in the answer.",
]
REJECT_COMMENTS = ["This topic is not in this term's syllabus.", "The same idea is already asked in an approved question."]


class ExamBankStep:
    """Mixed into the seed_connect_school command (uses self.rng, self.today, self.staff and self.owner_id)."""

    def _when(self, days_ago, hour=11):
        return datetime.combine(self.today - timedelta(days=days_ago), time(hour, self.rng.randint(0, 59)), tzinfo=ZONE)

    def _step_question_bank(self):
        from academics.models import AcademicLevel, Subject, SubjectAssignment
        from question_bank.models import Chapter

        level10 = AcademicLevel.objects.filter(name="Class 10").first()
        level8 = AcademicLevel.objects.filter(name="Class 8").first()
        if level10 is None or level8 is None:
            return "skipped: this school has no Class 8 or Class 10"
        maths = Subject.objects.filter(level=level10, code="MTH").first()
        science = Subject.objects.filter(level=level10, code="SCI").first()
        science8 = Subject.objects.filter(level=level8, code="SCI").first()
        english8 = Subject.objects.filter(level=level8, code="ENG").first()
        if not all((maths, science, science8, english8)):
            return "skipped: the expected Class 8 and Class 10 subjects are missing"
        if Chapter.objects.filter(subject=maths, name="Real Numbers").exists():
            return "skipped: the demo question bank already exists"

        def author_of(subject):
            assignment = (SubjectAssignment.objects.filter(subject=subject, instructor__isnull=False)
                          .select_related("instructor__staff_member__profile").order_by("section__name").first())
            staff = assignment.instructor.staff_member if assignment else None
            return staff if staff is not None and staff.profile.user_id else None

        authors = {s.id: author_of(s) for s in (maths, science, science8, english8)}
        if None in authors.values():
            return "skipped: a subject has no teacher with a login"
        reviewer = next((m for m in self.staff if m.designation == "Teacher" and m.profile.user_id
                         and m.id not in {a.id for a in authors.values()}), None)
        controller = next((m for m in self.staff if m.designation == "Administrative Officer" and m.profile.user_id), None) \
            or next((m for m in self.staff if m.designation != "Teacher" and m.profile.user_id), None)
        if reviewer is None or controller is None:
            return "skipped: no free teacher to review or office staff to prepare papers"

        self._grant_roles(authors.values(), reviewer, controller)
        from question_bank.models import SubjectReviewer

        for subject in (maths, science, science8, english8):
            SubjectReviewer.objects.get_or_create(subject=subject, staff=reviewer)

        chapters = {}
        for subject, plan in ((maths, content.MATHS_CHAPTERS), (science, content.SCIENCE_CHAPTERS),
                              (science8, content.SCIENCE8_CHAPTERS), (english8, content.ENGLISH8_CHAPTERS)):
            chapters[subject.id] = self._chapters(subject, plan)

        counts = {}
        maths_items = content.maths_questions(random.Random(self.rng.random()))
        plan = self._maths_states(maths_items)
        for item, state in zip(maths_items, plan):
            self._question(maths, chapters[maths.id], item, authors[maths.id], reviewer, state, counts)
        science_states = ["approved"] * 12 + ["submitted", "submitted", "changes_requested", "draft"]
        for item, state in zip(content.SCIENCE10, science_states):
            self._question(science, chapters[science.id], item, authors[science.id], reviewer, state, counts)
        for item, state in zip(content.SCIENCE8, ["approved", "submitted", "changes_requested", "draft"]):
            self._question(science8, chapters[science8.id], item, authors[science8.id], reviewer, state, counts)
        for item, state in zip(content.ENGLISH8, ["submitted", "rejected"]):
            self._question(english8, chapters[english8.id], item, authors[english8.id], reviewer, state, counts)

        papers = self._papers(maths, science, level10, controller, authors[maths.id])
        summary = ", ".join(f"{n} {s.replace('_', ' ')}" for s, n in sorted(counts.items()))
        return (f"{sum(counts.values())} questions ({summary}), {len(chapters)} subjects with chapters, reviewer "
                f"{reviewer.profile.first_name}; papers: {papers}")

    # --- people ------------------------------------------------------------------------------------------------

    def _grant_roles(self, authors, reviewer, controller):
        from roles.models import Permission, Role, UserRole

        for slug, (name, codenames) in ROLES.items():
            found = Permission.objects.filter(codename__in=codenames)
            if found.count() != len(codenames):
                raise RuntimeError(f"permissions missing for {name}: run the migrations first")
            role, _ = Role.objects.get_or_create(slug=slug, defaults={"name": name, "is_system_role": False,
                                                                       "description": f"Demo: {name.lower()} for the question bank"})
            role.permissions.set(found)
        holders = [(a, "qb-question-writer") for a in authors] + [(reviewer, "qb-question-reviewer"), (controller, "qb-exam-controller")]
        for staff, slug in holders:
            UserRole.objects.get_or_create(user_id=staff.profile.user_id, role=Role.objects.get(slug=slug))

    # --- chapters and questions ----------------------------------------------------------------------------------

    def _chapters(self, subject, plan):
        from question_bank.models import Chapter, Topic

        out = {}
        for order, (name, topics) in enumerate(plan, start=1):
            chapter = Chapter.objects.create(subject=subject, name=name, order=order)
            out[name] = (chapter, {t: Topic.objects.create(chapter=chapter, name=t, order=i) for i, t in enumerate(topics, start=1)})
        return out

    def _maths_states(self, items):
        """Approve enough of every kind for two non-overlapping sets per exam; vary the rest."""
        need = {("mcq", "easy"): 24, ("mcq", "medium"): 16, ("short", None): 16, ("long", None): 14}
        spare_states = ["submitted", "submitted", "changes_requested", "draft", "rejected", "archived", "submitted", "draft"]
        taken, states, spare = {}, [], iter(spare_states * 4)
        for item in items:
            key = (item["question_type"], item["difficulty"] if item["question_type"] == "mcq" else None)
            taken[key] = taken.get(key, 0) + 1
            if taken[key] <= need.get(key, 0):
                states.append("approved_after_changes" if self.rng.random() < 0.15 else "approved")
            else:
                states.append(next(spare))
        return states

    def _question(self, subject, chapters, item, author, reviewer, state, counts):
        from question_bank import services as qsvc
        from question_bank.models import Question, QuestionReview

        data = dict(item)
        chapter, topics = chapters[data.pop("chapter")]
        data.update(subject=subject, chapter=chapter, topic=topics.get(data.pop("topic", None)))
        data.setdefault("difficulty", "medium")
        data = qsvc.check_content(data)
        fields = ("subject", "chapter", "topic", "question_type", "difficulty", "marks", "body", "options", "answer",
                  "explanation", "marking_scheme", "learning_outcome")
        written_on = self._when(self.rng.randint(25, 70), hour=self.rng.randint(15, 20))
        question = Question.objects.create(
            **{k: data[k] for k in fields if k in data}, content_hash=qsvc.content_hash(subject.id, data["body"]),
            author=author, created_by_user_id=author.profile.user_id,
        )
        qsvc._save_version(question, author.profile.user_id)
        Question.objects.filter(pk=question.pk).update(created_at=written_on)

        def review(decision, comment, on):
            QuestionReview.objects.create(question=question, version=question.version, decision=decision, comment=comment,
                                          reviewer=reviewer, reviewer_user_id=reviewer.profile.user_id)
            QuestionReview.objects.filter(question=question, version=question.version, decision=decision).update(created_at=on)

        submitted_on = written_on + timedelta(days=self.rng.randint(1, 4))
        decided_on = submitted_on + timedelta(days=self.rng.randint(1, 5))
        final = state
        if state == "approved_after_changes":
            review(QuestionReview.Decision.CHANGES_REQUESTED, self.rng.choice(CHANGE_COMMENTS), decided_on)
            question.explanation = (question.explanation + " " if question.explanation else "") + "Working shown step by step."
            question.version += 1
            question.save(update_fields=["explanation", "version"])
            qsvc._save_version(question, author.profile.user_id)
            decided_on += timedelta(days=2)
            review(QuestionReview.Decision.APPROVED, "", decided_on)
            final = "approved"
        elif state in ("approved", "archived"):
            review(QuestionReview.Decision.APPROVED, "", decided_on)
        elif state == "changes_requested":
            review(QuestionReview.Decision.CHANGES_REQUESTED, self.rng.choice(CHANGE_COMMENTS), decided_on)
        elif state == "rejected":
            review(QuestionReview.Decision.REJECTED, self.rng.choice(REJECT_COMMENTS), decided_on)
        updates = {"status": final}
        if state != "draft":
            updates["submitted_at"] = submitted_on
        if state not in ("draft", "submitted"):
            updates.update(decided_at=decided_on, decided_by_user_id=reviewer.profile.user_id)
        Question.objects.filter(pk=question.pk).update(**updates)
        counts[final] = counts.get(final, 0) + 1

    # --- papers --------------------------------------------------------------------------------------------------

    def _papers(self, maths, science, level10, controller, maths_teacher):
        from examinations.models import Examination
        from question_bank import paper_services as psvc
        from question_bank.models import PaperAccessLog, PaperSection, QuestionPaper

        annual = Examination.objects.filter(name__startswith="Annual Examination").order_by("-start_date").first()
        if annual is None or annual.is_published:
            return "skipped (no unpublished Annual Examination)"
        pre_board = self._pre_board(annual, level10)
        approver = SimpleNamespace(user=SimpleNamespace(id=self.owner_id))
        prepared_by = controller.profile.user_id

        def paper(exam, subject, label, total, minutes, sections, seed):
            row = QuestionPaper.objects.create(
                examination=exam, subject=subject, set_label=label, title=f"{subject.name} - {exam.name}", total_marks=total,
                duration_minutes=minutes, prepared_by_user_id=prepared_by,
                instructions="All questions are compulsory. Section A carries 1 mark each, Section B 3 marks each and "
                             "Section C 8 marks each. Draw neat, labelled figures wherever needed.",
            )
            for order, (title, rules) in enumerate(sections, start=1):
                section = PaperSection.objects.create(paper=row, order=order, title=title)
                for count, kind, difficulty in rules:
                    section.rules.create(count=count, question_type=kind, difficulty=difficulty)
            if seed is not None:
                psvc.autofill(paper=row, seed=seed)
            return row

        def annual_layout():
            return [("Section A - Multiple choice", [(12, "mcq", "easy"), (8, "mcq", "medium")]),
                    ("Section B - Short answers", [(8, "short", "")]), ("Section C - Long answers", [(7, "long", "")])]

        def pre_board_layout():
            return [("Section A - Multiple choice", [(10, "mcq", "easy"), (6, "mcq", "medium")]),
                    ("Section B - Short answers", [(8, "short", "")]), ("Section C - Long answers", [(5, "long", "")])]

        notes = []
        # The Annual Examination (1 October): Set A released before the exam, Set B kept as a reserve, then withdrawn.
        a = paper(annual, maths, "A", 100, 180, annual_layout(), seed=11)
        b = paper(annual, maths, "B", 100, 180, annual_layout(), seed=12)
        for row in (a, b):
            psvc.submit(request=None, paper=row)
            psvc.approve(request=approver, paper=row)
        psvc.release(paper=a)
        psvc.withdraw(paper=b, reason="Reserve set not needed: Set A was used and the exam is over.")
        exam_day = datetime.combine(annual.start_date, time(8, 0), tzinfo=ZONE)
        QuestionPaper.objects.filter(pk=a.pk).update(submitted_at=exam_day - timedelta(days=12), approved_at=exam_day - timedelta(days=9),
                                                     released_at=exam_day - timedelta(minutes=30))
        QuestionPaper.objects.filter(pk=b.pk).update(submitted_at=exam_day - timedelta(days=12), approved_at=exam_day - timedelta(days=9),
                                                     withdrawn_at=exam_day + timedelta(days=8))
        opened = [(prepared_by, "paper", -10), (self.owner_id, "answer_key", -9), (maths_teacher.profile.user_id, "paper", 0),
                  (maths_teacher.profile.user_id, "answer_key", 3)]
        for user_id, kind, offset in opened:
            log = PaperAccessLog.objects.create(paper=a, user_id=user_id, kind=kind, status_at_access="released" if offset >= 0 else "approved")
            PaperAccessLog.objects.filter(pk=log.pk).update(created_at=exam_day + timedelta(days=offset, hours=2))
        notes.append("Annual Maths A released, B withdrawn")

        # The Pre-Board Examination (December): A approved for release on the exam morning, B waiting, Science a draft.
        if pre_board is not None:
            pa = paper(pre_board, maths, "A", 80, 180, pre_board_layout(), seed=21)
            pb = paper(pre_board, maths, "B", 80, 180, pre_board_layout(), seed=22)
            psvc.submit(request=None, paper=pa)
            psvc.approve(request=approver, paper=pa)
            psvc.schedule_release(paper=pa, release_at=datetime.combine(pre_board.start_date, time(8, 0), tzinfo=ZONE))
            psvc.submit(request=None, paper=pb)
            sci = paper(pre_board, science, "A", 80, 180, [("Section A - Multiple choice", [(10, "mcq", "")]),
                                                            ("Section B - Short answers", [(4, "short", "")])], seed=None)
            section = sci.sections.first()
            for question in psvc.eligible_questions(sci).filter(question_type="mcq")[:6]:
                psvc.add_question(paper=sci, section=section, question=question)
            notes.append("Pre-Board Maths A approved (releases on the exam morning), B waiting for approval, Science A draft")
        return "; ".join(notes)

    def _pre_board(self, annual, level10):
        """An upcoming Class 10 Pre-Board Examination in December, with 80-mark schedules for every Class 10 subject."""
        from academics.models import Section, Subject
        from examinations.models import Examination, ExamSchedule, ExamType

        start = date(self.today.year if self.today.month < 12 else self.today.year + 1, 12, 1)
        if start <= self.today:
            return None
        exam_type, _ = ExamType.objects.get_or_create(name="Pre-Board Examination", defaults={"order": 5})
        exam, created = Examination.objects.get_or_create(
            name=f"Pre-Board Examination {annual.academic_year}",
            defaults={"academic_year": annual.academic_year, "academic_year_ref": annual.academic_year_ref,
                      "exam_type": exam_type, "start_date": start, "end_date": start + timedelta(days=9)},
        )
        if created:
            subjects = list(Subject.objects.filter(level=level10).order_by("name"))
            for section in Section.objects.filter(level=level10):
                for slot, subject in enumerate(subjects):
                    ExamSchedule.objects.create(
                        examination=exam, academic_year=exam.academic_year, academic_year_ref=exam.academic_year_ref,
                        subject=subject, section=section, date=start + timedelta(days=slot), start_time=time(9, 30),
                        end_time=time(12, 45), max_marks=80, pass_marks=26,
                    )
        return exam

