"""seed_connect_school: connects an existing seeded school so every module has related data.

Builds a small ``sunrisevalley_school`` with seed_realistic_school, then runs the command. Creates tenant
schemas, so it needs a disposable PostgreSQL database and is meant to be run only in an isolated test stage.
"""
from collections import Counter
from datetime import timedelta

from django.core import mail
from django.core.management import call_command
from django.db import connection
from django.test import TransactionTestCase, override_settings
from django.utils import timezone
from django_tenants.utils import tenant_context

from organizations.models import Organization

SCHEMA = "sunrisevalley_school"


CERT_KEYS = {"CERTIFICATE_INTEGRITY_KEYS": "1:" + "k" * 48, "CERTIFICATE_INTEGRITY_ACTIVE_KEY": "1"}


@override_settings(**CERT_KEYS)
class SeedConnectSchoolTests(TransactionTestCase):
    @classmethod
    def _seed_school(cls):
        call_command("seed_realistic_school", students=40, seed=7, attendance_days=10, academic_years=2)

    def setUp(self):
        self.addCleanup(self._cleanup)
        self._cleanup()
        self._seed_school()
        self.org = Organization.objects.get(schema_name=SCHEMA)
        self.today = timezone.localdate()

    def _cleanup(self):
        try:
            call_command("seed_realistic_school", clear=True)
        except Exception:
            pass
        connection.set_schema_to_public()

    def run_command(self, **kwargs):
        call_command("seed_connect_school", **kwargs)
        connection.set_schema_to_public()

    # ---------------------------------------------------------------------------------------------------
    def test_everything_is_connected_and_a_second_run_changes_nothing(self):
        with tenant_context(self.org):
            from notifications.models import EmailOutboxEvent

            self.outbox_before = EmailOutboxEvent.objects.count()  # rows the base seeder wrote itself
        self.run_command()
        with tenant_context(self.org):
            snapshot = self.counts()
            self.check_accounts()
            self.check_staff_parents()
            self.check_payroll()
            self.check_transport()
            self.check_library()
            self.check_alerts()
            self.check_calendar_and_leave()
            self.check_timetable()
            self.check_announcements()
            self.check_certificates()
            self.check_admissions()
            self.check_inventory()
            self.check_question_bank()
        self.assertEqual(mail.outbox, [], "the seeder must never send real email")
        with tenant_context(self.org):
            from notifications.models import EmailOutboxEvent, Notification

            self.assertEqual(EmailOutboxEvent.objects.count(), self.outbox_before, "the seeder queues no email")
            self.assertTrue(Notification.objects.filter(category="leave").exists(), "in-app notices are still made")

        self.run_command()  # again: every step skips or finds nothing to add
        with tenant_context(self.org):
            self.assertEqual(self.counts(), snapshot)

    def test_a_single_step_can_run_alone_and_unknown_steps_are_refused(self):
        from django.core.management.base import CommandError

        with self.assertRaises(CommandError):
            self.run_command(steps="accounts,nonsense")
        with self.assertRaises(CommandError):
            call_command("seed_connect_school", schema="no_such_school")
        self.run_command(steps="library")
        with tenant_context(self.org):
            from library.models import BookCopy
            from payroll.models import SalaryComponent

            self.assertGreater(BookCopy.objects.count(), 0)
            self.assertEqual(SalaryComponent.objects.count(), 0)

    # --- helpers -------------------------------------------------------------------------------------------
    def counts(self):
        from accounts.models import User
        from families.models import Parent, StudentParentRelation
        from fees.models import Payment, StudentFee
        from library.models import Book, BookCopy, Fine, Loan
        from payroll.models import Payslip, PayrollRun
        from roles.models import UserRole
        from transport.models import StudentTransport, TransportBill

        from academics.models import CalendarEvent
        from announcements.models import Announcement
        from certificates.models import Certificate, IdCardToken
        from inventory.models import Item
        from staff.models import LeaveApplication
        from students.models import AdmissionApplication, AdmissionEnquiry
        from timetable.models import TimetableEntry, TimetableSubstitution

        from question_bank.models import PaperQuestion, Question, QuestionPaper

        return {
            "questions": Question.objects.count(), "papers": QuestionPaper.objects.count(),
            "paper_questions": PaperQuestion.objects.count(),
            "events": CalendarEvent.objects.count(), "leave": LeaveApplication.objects.count(),
            "timetable": TimetableEntry.objects.count(), "substitutions": TimetableSubstitution.objects.count(),
            "announcements": Announcement.objects.count(), "certificates": Certificate.objects.count(),
            "id_cards": IdCardToken.objects.count(), "enquiries": AdmissionEnquiry.objects.count(),
            "applications": AdmissionApplication.objects.count(), "items": Item.objects.count(),
            "users": User.objects.count(), "roles": UserRole.objects.count(), "parents": Parent.objects.count(),
            "relations": StudentParentRelation.objects.count(), "fees": StudentFee.objects.count(),
            "payments": Payment.objects.count(), "seats": StudentTransport.objects.count(),
            "bills": TransportBill.objects.count(), "books": Book.objects.count(), "copies": BookCopy.objects.count(),
            "loans": Loan.objects.count(), "fines": Fine.objects.count(), "runs": PayrollRun.objects.count(),
            "payslips": Payslip.objects.count(),
        }

    def check_accounts(self):
        from families.models import Parent
        from students.models import Student, StudentLevel

        parents = Parent.objects.filter(student_links__student__status="active").distinct().select_related("profile")
        self.assertGreater(parents.count(), 0)
        for parent in parents:
            self.assertIsNotNone(parent.profile.user_id, "every parent of an active student can sign in")
        from accounts.models import User

        self.assertEqual(User.objects.filter(email="").count(), 0, "a missing email is NULL, never an empty string")
        self.assertGreater(User.objects.filter(email__isnull=True, username__startswith="svc_p_").count(), 1, "several parents have no email")
        orders = {e.student_id: e.level.order for e in StudentLevel.objects.filter(is_current=True).select_related("level")}
        for student in Student.objects.filter(status="active").select_related("profile"):
            order = orders.get(student.id)
            if order is not None and order >= 9:
                self.assertIsNotNone(student.profile.user_id, f"{student.enrollment_id} is Class 6 or above")

    def check_staff_parents(self):
        from families.models import StudentParentRelation
        from roles.models import UserRole
        from staff.models import StaffMember

        staff_parents = [m for m in StaffMember.objects.select_related("profile") if hasattr(m.profile, "parent_record")]
        self.assertGreater(len(staff_parents), 0)
        for member in staff_parents:
            self.assertTrue(StudentParentRelation.objects.filter(parent__profile=member.profile).exists())
            self.assertTrue(UserRole.objects.filter(user_id=member.profile.user_id, role__slug="parent").exists())
        # one family never has two fathers or two mothers
        pairs = Counter(
            StudentParentRelation.objects.filter(relation_type__in=["father", "mother"]).values_list("student_id", "relation_type")
        )
        for (student_id, relation), n in pairs.items():
            self.assertEqual(n, 1, f"student {student_id} has {n} people recorded as {relation}")

    def check_payroll(self):
        from payroll.models import Payslip, PayrollRun, SalaryComponent, StaffSalary
        from staff.models import StaffMember

        self.assertEqual(SalaryComponent.objects.count(), 5)
        active = StaffMember.objects.filter(is_active=True)
        for member in active:
            self.assertTrue(StaffSalary.objects.filter(staff=member).exists(), f"{member.employee_id} has a salary")
        runs = {r.status: r for r in PayrollRun.objects.all()}
        self.assertEqual(set(runs), {"paid", "calculated"})
        self.assertEqual(runs["paid"].period_end.month, (runs["calculated"].period_start - timedelta(days=1)).month)
        for run in runs.values():
            self.assertEqual(Payslip.objects.filter(run=run).count(), active.count())

    def check_transport(self):
        from fees.models import StudentFee
        from transport.models import Route, StudentTransport, TransportBill, Vehicle

        self.assertGreaterEqual(Vehicle.objects.count(), 3)
        for route in Route.objects.select_related("vehicle"):
            taken = StudentTransport.objects.filter(route=route, end_date__isnull=True).count()
            self.assertLessEqual(taken, route.vehicle.capacity, f"{route.name} is within its bus capacity")
        for seat in StudentTransport.objects.select_related("stop"):
            self.assertEqual(seat.stop is None, not seat.route.stops.exists(), "a seat has a stop exactly when the route has stops")
        for bill in TransportBill.objects.select_related("student_fee"):
            self.assertEqual(bill.student_fee.fee_head.name, "Transport")
            self.assertEqual(bill.student_fee.amount_due, bill.amount)
        self.assertEqual(
            TransportBill.objects.count(),
            TransportBill.objects.values("student", "month").distinct().count(),
        )
        self.assertEqual(StudentFee.objects.filter(transport_bill__isnull=False).count(), TransportBill.objects.count())

    def check_library(self):
        from library.models import BookCopy, Fine, Loan

        self.assertGreater(BookCopy.objects.count(), 40)
        open_loans = Loan.objects.filter(returned_on__isnull=True)
        self.assertEqual(open_loans.count(), open_loans.values("copy").distinct().count(), "one open loan per copy")
        for loan in open_loans:
            self.assertEqual(loan.copy.status, "issued")
        self.assertTrue(open_loans.filter(due_on__lt=self.today).exists(), "some loans are overdue")
        self.assertTrue(Fine.objects.filter(status="pending").exists())
        for fine in Fine.objects.filter(status="billed"):
            self.assertIsNotNone(fine.student_fee_id)
            self.assertEqual(fine.student_fee.amount_due, fine.amount)

    def check_alerts(self):
        from notifications.models import NotificationSettings

        settings = NotificationSettings.load()
        self.assertTrue(settings.absence_alerts_enabled)
        self.assertTrue(settings.payment_receipts_enabled)
        self.assertFalse(settings.fee_reminders_enabled)

    def check_calendar_and_leave(self):
        from academics.models import CalendarEvent
        from attendance.models import StaffAttendance
        from staff.models import LeaveApplication, StaffLeaveBalance

        holidays = CalendarEvent.objects.filter(is_holiday=True, status="PUBLISHED")
        self.assertGreater(holidays.count(), 5)
        holiday_days = set()
        for event in holidays:
            day = event.start_date
            while day <= event.end_date:
                holiday_days.add(day)
                day += timedelta(days=1)
        marked_on_holiday = StaffAttendance.objects.filter(date__in=holiday_days).exclude(remarks__contains="[LEAVE_APP:")
        self.assertEqual(marked_on_holiday.count(), 0, "no staff attendance is marked on a school holiday")

        from core.models import AuditLog

        actions = set(AuditLog.objects.filter(model_name="LeaveApplication").values_list("action", flat=True))
        self.assertTrue({"CREATE", "APPROVE"} <= actions, f"leave actions are audited without a web request: {actions}")
        statuses = set(LeaveApplication.objects.values_list("status", flat=True))
        self.assertTrue({"approved", "pending"} <= statuses, statuses)
        for balance in StaffLeaveBalance.objects.all():
            self.assertLessEqual(balance.used_days + balance.pending_days, balance.allocated_days)
        for application in LeaveApplication.objects.filter(status="approved"):
            marks = StaffAttendance.objects.filter(
                staff=application.staff, date__gte=application.start_date, date__lte=application.end_date, status="leave"
            )
            self.assertTrue(marks.exists() or application.working_days == 0, "approved leave shows as leave in attendance")

    def check_timetable(self):
        from academics.models import SubjectAssignment
        from timetable.models import Period, TimetableEntry, TimetableSubstitution

        self.assertGreater(Period.objects.filter(is_break=False).count(), 0)
        self.assertGreater(TimetableEntry.objects.count(), 0)
        for entry in TimetableEntry.objects.select_related("period"):
            self.assertFalse(entry.period.is_break)
            self.assertTrue(
                SubjectAssignment.objects.filter(section=entry.section, subject=entry.subject, instructor=entry.instructor).exists(),
                "every timetable slot uses the teacher assigned to that subject and class",
            )
        for sub in TimetableSubstitution.objects.select_related("timetable_entry"):
            entry = sub.timetable_entry
            clash = TimetableEntry.objects.filter(
                instructor=sub.substitute_instructor, day_of_week=entry.day_of_week, period=entry.period, academic_year=entry.academic_year
            )
            self.assertFalse(clash.exists(), "a substitute is free at that period")

    def check_announcements(self):
        from announcements.models import Announcement, AnnouncementRecipient
        from notifications.models import Notification

        states = Counter(Announcement.objects.values_list("status", flat=True))
        for state in ("published", "scheduled", "draft", "archived"):
            self.assertGreater(states[state], 0, f"there is a {state} announcement")
        for row in Announcement.objects.filter(status__in=["published", "archived"]):
            self.assertGreater(AnnouncementRecipient.objects.filter(announcement=row).count(), 0)
            self.assertGreater(Notification.objects.filter(link=f"/dashboard/announcements/{row.id}").count(), 0)
            self.assertFalse(row.send_email)

    def check_certificates(self):
        from certificates import services
        from certificates.models import Certificate, IdCardToken

        certificates = list(Certificate.objects.all())
        self.assertGreater(len(certificates), 0)
        kinds = {c.certificate_type for c in certificates}
        self.assertTrue({"bonafide", "character", "experience"} <= kinds, kinds)
        self.assertEqual(len({c.certificate_number for c in certificates}), len(certificates))
        for cert in certificates:
            self.assertTrue(services.verify_integrity(cert), f"{cert.certificate_number} verifies")
        self.assertTrue(Certificate.objects.filter(status="cancelled").exists())
        self.assertGreater(IdCardToken.objects.count(), 0)

    def check_admissions(self):
        from students.models import AdmissionApplication, AdmissionEnquiry, AdmissionInterview

        self.assertGreater(AdmissionEnquiry.objects.count(), 20)
        for enquiry in AdmissionEnquiry.objects.filter(status="converted"):
            self.assertTrue(AdmissionApplication.objects.filter(enquiry=enquiry).exists())
        statuses = set(AdmissionApplication.objects.values_list("status", flat=True))
        self.assertTrue({"submitted", "approved", "rejected", "waitlisted"} <= statuses, statuses)
        for application in AdmissionApplication.objects.filter(status="rejected"):
            self.assertTrue(application.decision_reason)
        self.assertGreater(AdmissionInterview.objects.count(), 0)

    def check_inventory(self):
        from inventory.models import Asset, Item

        self.assertGreater(Item.objects.count(), 0)
        self.assertGreater(Asset.objects.count(), 0)

    def check_question_bank(self):
        from collections import Counter as Tally

        from question_bank import paper_services
        from question_bank.models import PaperQuestion, Question, QuestionPaper, QuestionReview, QuestionVersion, SubjectReviewer
        from roles.models import UserRole

        states = Tally(Question.objects.values_list("status", flat=True))
        for state in ("approved", "submitted", "changes_requested", "rejected", "draft", "archived"):
            self.assertGreater(states[state], 0, f"there is a {state} question")
        self.assertGreater(states["approved"], 60)
        for question in Question.objects.exclude(status="draft"):
            self.assertIsNotNone(question.submitted_at)
        self.assertEqual(QuestionVersion.objects.filter(number__gt=1).count(), Question.objects.filter(version__gt=1).count())
        for review in QuestionReview.objects.select_related("question"):
            self.assertNotEqual(review.reviewer_user_id, review.question.created_by_user_id, "nobody reviews their own question")
        for row in SubjectReviewer.objects.select_related("staff__profile"):
            self.assertTrue(UserRole.objects.filter(user_id=row.staff.profile.user_id, role__slug="qb-question-reviewer").exists())

        papers = {(p.examination.name.split(" ")[0], p.subject.name, p.set_label): p for p in QuestionPaper.objects.select_related("examination", "subject")}
        statuses = Tally(p.status for p in papers.values())
        self.assertEqual(statuses, Tally({"released": 1, "withdrawn": 1, "approved": 1, "submitted": 1, "draft": 1}))
        for paper in papers.values():
            if paper.status in ("approved", "released", "withdrawn"):
                self.assertIsNotNone(paper.frozen_content)
                self.assertNotEqual(paper.approved_by_user_id, paper.prepared_by_user_id)
            if paper.status in ("submitted", "approved", "released"):
                self.assertEqual(paper_services.problems(paper), [], f"{paper} is complete")
        pre_a = papers[("Pre-Board", "Mathematics", "A")]
        self.assertIsNotNone(pre_a.release_at)
        self.assertFalse(paper_services.is_released(pre_a))
        a_ids = set(PaperQuestion.objects.filter(paper=pre_a).values_list("question_id", flat=True))
        b_ids = set(PaperQuestion.objects.filter(paper=papers[("Pre-Board", "Mathematics", "B")]).values_list("question_id", flat=True))
        self.assertEqual(a_ids & b_ids, set(), "two live sets share no question")
        self.assertTrue(papers[("Annual", "Mathematics", "A")].access_log.exists())
        self.assertGreater(len(paper_services.problems(papers[("Pre-Board", "Science", "A")])), 0, "the Science draft is still in progress")
