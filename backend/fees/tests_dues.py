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


class CallLogTests(ReminderFixture):
    """Calls about unpaid fees, promises to pay, and how a promise is kept or broken."""

    def _user(self, name, codenames=None, owner=False):
        from accounts.models import User
        from roles.constants import SYSTEM_PERMISSIONS
        from roles.models import Permission

        with tenant_context(self.school):
            seed_default_roles()
            for p in SYSTEM_PERMISSIONS:
                Permission.objects.get_or_create(
                    codename=p["codename"], defaults={"name": p["name"], "module": p["module"], "description": p["description"]}
                )
            user = User.objects.create_user(username=f"frm_{name}", email=f"frm_{name}@rem.test", password="Pass1234!")
            if owner:
                role = Role.objects.get(slug="owner")
            else:
                role = Role.objects.create(name=name, slug=f"role-{name}", is_system_role=False)
                role.permissions.set(Permission.objects.filter(codename__in=codenames or []))
            UserRole.objects.create(user=user, role=role)
        return user

    def _api(self, view, user, method="get", data=None, **kwargs):
        factory = APIRequestFactory()
        request = factory.get("/x/", data or {}) if method == "get" else factory.post("/x/", data or {}, format="json")
        request.tenant = self.school
        force_authenticate(request, user=user)
        with tenant_context(self.school):
            return view.as_view()(request, **kwargs)

    def _call(self, user, **body):
        from .views import StudentCallsView

        return self._api(StudentCallsView, user, "post", body, student_id=self.student.pk)

    def _day(self, n):
        from core.dates import school_today

        return school_today() + timedelta(days=n)

    def test_a_call_is_recorded_with_who_made_it_and_only_people_who_collect_payments_may_write_one(self):
        from .views import StudentCallsView

        collector = self._user("collector", ["collect_payments", "view_financial_reports"])
        viewer = self._user("viewer", ["view_financial_reports"])
        nobody = self._user("nobody", [])
        self.assertEqual(self._call(viewer, outcome="reached", note="Spoke to the father").status_code, 403)
        self.assertEqual(self._call(nobody, outcome="reached", note="x").status_code, 403)
        ok = self._call(collector, outcome="no_answer", note="  Phone was off  ")
        self.assertEqual(ok.status_code, 201, ok.data)
        self.assertEqual((ok.data[0]["note"], ok.data[0]["by"], ok.data[0]["promise"]), ("Phone was off", "frm_collector", None))
        self.assertEqual(self._api(StudentCallsView, viewer, student_id=self.student.pk).status_code, 200)  # a viewer can read
        self.assertEqual(self._api(StudentCallsView, nobody, student_id=self.student.pk).status_code, 403)

    def test_bad_calls_are_refused_and_a_student_who_owes_nothing_cannot_be_called_about(self):
        owner = self._user("boss", owner=True)
        self.assertEqual(self._call(owner, outcome="shrugged", note="x").status_code, 400)
        self.assertEqual(self._call(owner, outcome="reached", note="   ").status_code, 400)
        self.assertEqual(self._call(owner, outcome="reached", note="x" * 501).status_code, 400)
        self.assertEqual(self._call(owner, outcome="promised", note="Will pay").status_code, 400)  # no date
        self.assertEqual(self._call(owner, outcome="promised", note="x", promise_date=self._day(-1).isoformat()).status_code, 400)
        self.assertEqual(self._call(owner, outcome="promised", note="x", promise_date=self._day(200).isoformat()).status_code, 400)
        self.assertEqual(self._call(owner, outcome="promised", note="x", promise_date="soon").status_code, 400)
        later = self._day(3).isoformat()
        for bad in ("abc", "0", "-5", "99999"):
            self.assertEqual(self._call(owner, outcome="promised", note="x", promise_date=later, promise_amount=bad).status_code, 400, bad)
        self._pay(self.school, self.fee, "1500.00")
        self.assertEqual(self._call(owner, outcome="reached", note="x").status_code, 400)  # nothing owed now
        with tenant_context(self.school):
            from .models import FeeCallNote

            self.assertEqual(FeeCallNote.objects.count(), 0)  # refusals wrote nothing

    def test_a_promise_is_pending_until_its_date_then_kept_if_paid_or_broken_if_not(self):
        from .followups import history, latest_for

        owner = self._user("boss", owner=True)
        made = self._call(owner, outcome="promised", note="Father will pay Friday", promise_date=self._day(2).isoformat(), promise_amount="1000")
        self.assertEqual(made.status_code, 201, made.data)
        with tenant_context(self.school):
            self.assertEqual(history(self.student.pk)[0]["promise"]["status"], "pending")
            self.assertEqual(latest_for([self.student.pk], self._day(2))[self.student.pk]["promise"]["status"], "pending")  # the day itself is still fine
            self.assertEqual(latest_for([self.student.pk], self._day(3))[self.student.pk]["promise"]["status"], "broken")  # a day late
        self._pay(self.school, self.fee, "400.00")  # part-payment is not enough
        with tenant_context(self.school):
            self.assertEqual(latest_for([self.student.pk], self._day(3))[self.student.pk]["promise"]["status"], "broken")
        self._pay(self.school, self.fee, "600.00")  # now 1000 has come in since the call
        with tenant_context(self.school):
            self.assertEqual(latest_for([self.student.pk], self._day(3))[self.student.pk]["promise"]["status"], "kept")

    def test_a_payment_made_before_the_call_does_not_count_towards_the_promise(self):
        from .followups import latest_for

        owner = self._user("boss", owner=True)
        self._pay(self.school, self.fee, "300.00")  # paid before anyone called
        self._call(owner, outcome="promised", note="Will pay the rest", promise_date=self._day(1).isoformat(), promise_amount="500")
        with tenant_context(self.school):
            self.assertEqual(latest_for([self.student.pk], self._day(2))[self.student.pk]["promise"]["status"], "broken")

    def test_a_newer_promise_replaces_an_older_one_and_a_promise_without_an_amount_is_kept_by_any_payment(self):
        from .followups import history, latest_for

        owner = self._user("boss", owner=True)
        self._call(owner, outcome="promised", note="first", promise_date=self._day(1).isoformat())
        self._call(owner, outcome="promised", note="second", promise_date=self._day(10).isoformat(), promise_amount="200")
        with tenant_context(self.school):
            rows = history(self.student.pk)
            self.assertEqual([r["note"] for r in rows], ["second", "first"])
            self.assertEqual(rows[1]["promise"]["status"], "replaced")
            self.assertEqual(latest_for([self.student.pk], self._day(0))[self.student.pk]["promise"]["amount"], Decimal("200.00"))
        self._call(owner, outcome="promised", note="third, no amount", promise_date=self._day(5).isoformat())
        self._pay(self.school, self.fee, "1.00")
        with tenant_context(self.school):
            self.assertEqual(latest_for([self.student.pk], self._day(0))[self.student.pk]["promise"]["status"], "kept")

    def test_the_dues_list_shows_the_last_call_and_promise_and_filters_by_promise(self):
        from .views import DuesByStudentView, StudentCallsView

        owner = self._user("boss", owner=True)
        other = self._student(self.school, "ENR-D-2")
        self._fee(self.school, other, amount="800.00")
        third = self._student(self.school, "ENR-D-3")
        self._fee(self.school, third, amount="900.00")
        self._call(owner, outcome="promised", note="will pay", promise_date=self._day(2).isoformat(), promise_amount="500")
        self._api(StudentCallsView, owner, "post", {"outcome": "no_answer", "note": "off"}, student_id=other.pk)

        def listing(**params):
            return {r["enrollment_id"]: r for r in self._api(DuesByStudentView, owner, data=params).data["results"]}

        everyone = listing()
        self.assertEqual(everyone["ENR-R-1"]["last_outcome"], "promised")
        self.assertEqual(everyone["ENR-R-1"]["promise"]["status"], "pending")
        self.assertEqual((everyone["ENR-D-2"]["last_outcome"], everyone["ENR-D-2"]["promise"]), ("no_answer", None))
        self.assertIsNone(everyone["ENR-D-3"]["last_call_at"])
        self.assertEqual(list(listing(promise="pending")), ["ENR-R-1"])
        self.assertEqual(sorted(listing(promise="none")), ["ENR-D-2", "ENR-D-3"])
        self.assertEqual(listing(promise="broken"), {})
        self.assertEqual(self._api(DuesByStudentView, owner, data={"promise": "maybe"}).status_code, 400)


class DeskTests(ReminderFixture):
    """The follow-up desk and the morning reminder. 'Today' is injected; calls are written straight to the table so
    their dates can be set."""

    _user = CallLogTests._user
    _api = CallLogTests._api

    def _day(self, n):
        from core.dates import school_today

        return school_today() + timedelta(days=n)

    def _student_owing(self, label, *, due, amount="1000.00"):
        student = self._student(self.school, f"ENR-F-{label}")
        self._fee(self.school, student, due=due, amount=amount)
        return student

    def _note(self, student, *, outcome="reached", created_days_ago=0, promise_date=None, promise_amount=None):
        from django.utils import timezone

        from .models import FeeCallNote

        with tenant_context(self.school):
            note = FeeCallNote.objects.create(
                student=student, outcome=outcome, note="n", promise_date=promise_date, promise_amount=promise_amount
            )
            FeeCallNote.objects.filter(pk=note.pk).update(created_at=timezone.now() - timedelta(days=created_days_ago))
            return note

    def test_the_desk_sorts_families_into_broken_due_today_and_uncalled(self):
        from . import followups

        today = self._day(0)
        old = today - timedelta(days=60)
        broken = self._student_owing("BRK", due=old, amount="900.00")
        self._note(broken, outcome="promised", created_days_ago=10, promise_date=today - timedelta(days=3), promise_amount=Decimal("500"))
        due_today = self._student_owing("TDY", due=old, amount="700.00")
        self._note(due_today, outcome="promised", created_days_ago=2, promise_date=today)
        future = self._student_owing("FUT", due=old)
        self._note(future, outcome="promised", created_days_ago=1, promise_date=today + timedelta(days=5))
        never_called = self._student_owing("NEV", due=old - timedelta(days=30))
        called_long_ago = self._student_owing("OLD", due=old)
        self._note(called_long_ago, created_days_ago=20)
        called_recently = self._student_owing("REC", due=old)
        self._note(called_recently, created_days_ago=3)
        not_yet_due = self._student_owing("NYD", due=today + timedelta(days=10))
        with tenant_context(self.school):
            got = followups.desk(today)
        ids = lambda key: [r["enrollment_id"] for r in got[key]]
        self.assertEqual(ids("broken"), ["ENR-F-BRK"])
        self.assertEqual(ids("due_today"), ["ENR-F-TDY"])
        uncalled = ids("uncalled")
        self.assertIn("ENR-F-NEV", uncalled)
        self.assertIn("ENR-F-OLD", uncalled)
        for left_out in ("ENR-F-REC", "ENR-F-FUT", "ENR-F-NYD", "ENR-F-BRK", "ENR-F-TDY"):
            self.assertNotIn(left_out, uncalled)  # recently called, promised, or not yet due
        self.assertEqual(got["summary"], {"broken": 1, "due_today": 1, "uncalled": len(uncalled)})
        self.assertEqual(uncalled[0], "ENR-R-1")  # the fixture's own student has the oldest due date, so is first

    def test_a_kept_promise_leaves_the_desk(self):
        from . import followups

        today = self._day(0)
        student = self._student_owing("KPT", due=today - timedelta(days=40), amount="800.00")
        self._note(student, outcome="promised", created_days_ago=10, promise_date=today - timedelta(days=2), promise_amount=Decimal("300"))
        with tenant_context(self.school):
            fee = student.fees.get()
        self._pay(self.school, fee, "300.00")
        with tenant_context(self.school):
            got = followups.desk(today)
        self.assertNotIn("ENR-F-KPT", [r["enrollment_id"] for r in got["broken"]])
        self.assertEqual(got["summary"]["broken"], 0)

    def test_the_api_serves_the_desk_to_people_who_see_financial_reports_only(self):
        from .views import FollowUpDeskView

        viewer = self._user("viewer", ["view_financial_reports"])
        nobody = self._user("nobody", [])
        self.assertEqual(self._api(FollowUpDeskView, nobody).status_code, 403)
        ok = self._api(FollowUpDeskView, viewer)
        self.assertEqual(ok.status_code, 200, ok.data)
        self.assertEqual(set(ok.data), {"broken", "due_today", "uncalled", "summary"})

    def test_the_morning_reminder_goes_once_to_each_person_who_collects_payments_and_only_with_something_to_say(self):
        from notifications.models import Notification

        from . import followups

        today = self._day(0)
        collector = self._user("collector", ["collect_payments"])
        viewer = self._user("viewer", ["view_financial_reports"])  # may see, may not collect: not reminded
        with tenant_context(self.school):
            self.assertEqual(followups.remind_accountants(today)["people"], 0)  # nothing broken or due
        broken = self._student_owing("BRK", due=today - timedelta(days=60))
        self._note(broken, outcome="promised", created_days_ago=10, promise_date=today - timedelta(days=3))
        due = self._student_owing("TDY", due=today - timedelta(days=60))
        self._note(due, outcome="promised", created_days_ago=2, promise_date=today)
        with tenant_context(self.school):
            first = followups.remind_accountants(today)
            self.assertEqual((first["people"], first["broken"], first["due_today"]), (1, 1, 1))
            notice = Notification.objects.get(recipient_user_id=collector.id, category="fees")
            self.assertIn("1 broken promise", notice.body)
            self.assertIn("1 promise due today", notice.body)
            self.assertEqual(notice.link, "/dashboard/fees/follow-ups")
            self.assertFalse(Notification.objects.filter(recipient_user_id=viewer.id, category="fees").exists())
            again = followups.remind_accountants(today)
            self.assertEqual((again["people"], again["already_reminded"]), (0, 1))
            self.assertEqual(Notification.objects.filter(category="fees", title="Fee follow-ups").count(), 1)

    def test_the_daily_task_runs_across_schools(self):
        from . import tasks

        today = self._day(0)
        collector = self._user("collector", ["collect_payments"])
        broken = self._student_owing("BRK", due=today - timedelta(days=60))
        self._note(broken, outcome="promised", created_days_ago=10, promise_date=today - timedelta(days=3))
        self.assertGreaterEqual(tasks.remind_fee_followups(), 1)
        with tenant_context(self.school):
            from notifications.models import Notification

            self.assertTrue(Notification.objects.filter(recipient_user_id=collector.id, category="fees").exists())
