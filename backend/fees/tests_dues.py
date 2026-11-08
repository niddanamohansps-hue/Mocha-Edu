"""The dues-by-student list: one row per student, aged by the oldest unpaid fee. Creates tenant schemas, so it needs
a disposable PostgreSQL database. "Today" is injected."""
from datetime import date, timedelta
from decimal import Decimal

from django_tenants.utils import tenant_context
from rest_framework.test import APIRequestFactory, force_authenticate

from academics.models import AcademicLevel, Program, Section
from roles.models import Role, UserRole
from roles.signals import seed_default_roles
from students.models import StudentLevel

from . import dues
from .models import FeeHead, StudentFee
from .tests_reminders import DUE, ReminderFixture
from .views import DuesByStudentView

TODAY = DUE + timedelta(days=45)  # the fixture's fee is 45 days late: the 31-60 band


class DuesTests(ReminderFixture):
    def setUp(self):
        super().setUp()
        with tenant_context(self.school):
            guardian = self.student.parent_links.get().parent.profile
            guardian.first_name, guardian.last_name, guardian.phone = "Mina", "Rai", "+919811112222"
            guardian.save()

    def _other(self, label, *, due, amount="1000.00"):
        student = self._student(self.school, f"ENR-D-{label}")
        fee = self._fee(self.school, student, due=due, amount=amount)
        return student, fee

    def _rows(self, **filters):
        with tenant_context(self.school):
            return dues.dues_by_student(today=TODAY, **filters)

    def test_each_student_is_one_row_aged_by_the_oldest_unpaid_fee_with_the_guardians_phone(self):
        with tenant_context(self.school):
            head = FeeHead.objects.get_or_create(name="Transport")[0]
        self._fee(self.school, self.student, due=TODAY + timedelta(days=10), amount="400.00", head=head)  # not yet due
        got = self._rows()
        row = next(r for r in got["results"] if r["enrollment_id"] == "ENR-R-1")
        self.assertEqual((row["outstanding"], row["overdue"], row["fees"]), (Decimal("1900.00"), Decimal("1500.00"), 2))
        self.assertEqual((row["oldest_due"], row["days_late"], row["band"]), (DUE, 45, "31-60"))
        self.assertEqual((row["guardian_name"], row["guardian_phone"], row["guardian_relation"]), ("Mina Rai", "+919811112222", "guardian"))

    def test_only_real_outstanding_money_counts_partly_paid_paid_and_cancelled_are_handled(self):
        part, fee = self._other("PART", due=DUE, amount="1000.00")
        self._pay(self.school, fee, "400.00")
        paid, paid_fee = self._other("PAID", due=DUE)
        self._pay(self.school, paid_fee, "1000.00")
        gone, gone_fee = self._other("GONE", due=DUE)
        with tenant_context(self.school):
            StudentFee.objects.filter(pk=gone_fee.pk).update(status="cancelled")
        got = self._rows()
        names = {r["enrollment_id"]: r for r in got["results"]}
        self.assertEqual(names["ENR-D-PART"]["outstanding"], Decimal("600.00"))
        self.assertNotIn("ENR-D-PAID", names)
        self.assertNotIn("ENR-D-GONE", names)

    def test_the_band_totals_age_money_fee_by_fee_and_add_up_to_the_outstanding_total(self):
        self._other("A", due=TODAY - timedelta(days=10), amount="100.00")   # 1-30
        self._other("B", due=TODAY - timedelta(days=75), amount="200.00")   # 61-90
        self._other("C", due=TODAY - timedelta(days=400), amount="300.00")  # 90+
        self._other("D", due=TODAY + timedelta(days=5), amount="50.00")     # current (not yet due)
        got = self._rows()
        bands = got["totals"]["bands"]
        self.assertEqual(
            (bands["current"], bands["1-30"], bands["31-60"], bands["61-90"], bands["90+"]),
            (Decimal("50.00"), Decimal("100.00"), Decimal("1500.00"), Decimal("200.00"), Decimal("300.00")),
        )
        self.assertEqual(sum(bands.values()), got["totals"]["outstanding"])
        self.assertEqual(got["totals"]["outstanding"], Decimal("2150.00"))
        self.assertEqual(got["totals"]["overdue"], Decimal("2100.00"))
        self.assertEqual(got["totals"]["students"], 5)

    def test_band_search_and_sort_filter_and_order_the_list_and_the_totals_follow(self):
        self._other("A", due=TODAY - timedelta(days=10), amount="100.00")
        self._other("C", due=TODAY - timedelta(days=400), amount="300.00")
        oldest = self._rows(sort="age")["results"][0]
        self.assertEqual((oldest["enrollment_id"], oldest["band"]), ("ENR-D-C", "90+"))
        biggest = self._rows(sort="amount")["results"][0]
        self.assertEqual(biggest["enrollment_id"], "ENR-R-1")
        only = self._rows(band="1-30")
        self.assertEqual([r["enrollment_id"] for r in only["results"]], ["ENR-D-A"])
        self.assertEqual((only["totals"]["students"], only["totals"]["outstanding"]), (1, Decimal("100.00")))
        self.assertEqual(only["totals"]["bands"]["31-60"], Decimal("0"))  # totals follow the filter
        found = self._rows(search="enr-d-c")
        self.assertEqual([r["enrollment_id"] for r in found["results"]], ["ENR-D-C"])
        by_name = self._rows(sort="name")["results"]
        self.assertEqual([r["name"] for r in by_name], sorted(r["name"] for r in by_name))

    def test_class_and_section_filters_use_the_current_enrolment(self):
        with tenant_context(self.school):
            program = Program.objects.create(name="Primary", code="PRI")
            level = AcademicLevel.objects.create(program=program, name="Grade 1", order=1)
            section = Section.objects.create(level=level, name="A")
            other_level = AcademicLevel.objects.create(program=program, name="Grade 2", order=2)
            StudentLevel.objects.create(student=self.student, level=level, section=section, academic_year="2026", is_current=True)
        other, _ = self._other("X", due=DUE)
        with tenant_context(self.school):
            StudentLevel.objects.create(student=other, level=other_level, academic_year="2026", is_current=True)
        mine = self._rows(level=level.id)
        self.assertEqual([r["enrollment_id"] for r in mine["results"]], ["ENR-R-1"])
        self.assertEqual((mine["results"][0]["level"], mine["results"][0]["section"]), ("Grade 1", "A"))
        self.assertEqual([r["enrollment_id"] for r in self._rows(section=section.id)["results"]], ["ENR-R-1"])
        self.assertEqual(self._rows(level=other_level.id)["results"][0]["enrollment_id"], "ENR-D-X")

    def test_the_list_pages_and_a_student_with_no_guardian_still_appears(self):
        for label in "ABC":
            self._other(label, due=DUE)
        first = self._rows(page=1, page_size=2)
        self.assertEqual((first["count"], len(first["results"])), (4, 2))
        self.assertEqual(len(self._rows(page=2, page_size=2)["results"]), 2)
        self.assertEqual(self._rows(page=3, page_size=2)["results"], [])
        lonely = next(r for r in self._rows()["results"] if r["enrollment_id"] == "ENR-D-A")
        self.assertEqual((lonely["guardian_name"], lonely["guardian_phone"]), ("", ""))

    def test_the_academic_year_filter_leaves_other_years_out(self):
        with tenant_context(self.school):
            StudentFee.objects.filter(pk=self.fee.pk).update(academic_year="2025")
        self.assertEqual(self._rows()["count"], 1)
        self.assertEqual(self._rows(academic_year="2026")["count"], 0)
        self.assertEqual(self._rows(academic_year="2025")["count"], 1)


class DuesApiTests(ReminderFixture):
    def _call(self, user, params=None):
        request = APIRequestFactory().get("/x/", params or {})
        request.tenant = self.school
        force_authenticate(request, user=user)
        with tenant_context(self.school):
            return DuesByStudentView.as_view()(request)

    def _owner(self):
        from accounts.models import User

        with tenant_context(self.school):
            seed_default_roles()
            user = User.objects.create_user(username="frm_owner", email="frm_owner@rem.test", password="Pass1234!")
            UserRole.objects.create(user=user, role=Role.objects.get(slug="owner"))
        return user

    def test_only_people_who_may_see_financial_reports_can_read_it_and_bad_filters_are_refused(self):
        self.assertEqual(self._call(self.student_user).status_code, 403)
        owner = self._owner()
        ok = self._call(owner)
        self.assertEqual(ok.status_code, 200, ok.data)
        self.assertEqual(ok.data["count"], 1)
        for bad in ({"band": "ancient"}, {"sort": "mood"}, {"level": "not-a-uuid"}, {"page": "x"}):
            self.assertEqual(self._call(owner, bad).status_code, 400, bad)
        capped = self._call(owner, {"page_size": "9999"})
        self.assertEqual(capped.status_code, 200)
