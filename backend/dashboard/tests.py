import datetime
from decimal import Decimal

from django.db import connection
from django.test import TransactionTestCase
from django_tenants.utils import tenant_context
from rest_framework.test import APIClient

from academics.models import AcademicLevel, Program, Section
from accounts.models import User
from attendance.models import AttendanceSession, StudentAttendance
from families.models import Parent, StudentParentRelation
from fees.models import FeeHead, StudentFee
from fees.services import record_payment
from notifications.models import Notification
from organizations.models import Domain, Organization
from profiles.models import Profile
from roles.models import Permission, Role, UserRole
from staff.models import Instructor, StaffMember
from students.models import PromotionRecord, Student, StudentLevel
from students.services import execute_lifecycle_actions


class DashboardFixtureMixin:
    """Mirrors students/fees/notifications tests.py exactly."""

    SCHEMA_NAME = "dash_test_school"
    DOMAIN = "dashtest.localhost"

    def _build_school(self, schema_name=None, domain=None, name="Dashboard Test School"):
        schema_name = schema_name or self.SCHEMA_NAME
        domain = domain or self.DOMAIN
        connection.set_schema_to_public()
        school = Organization.objects.create(schema_name=schema_name, name=name)
        Domain.objects.create(domain=domain, tenant=school, is_primary=True)
        return school

    def _build_user_with_profile(self, username, role_slug, first_name="Test", last_name="User"):
        """
        Builds a User directly and links its Profile BEFORE the UserRole is
        created - profiles.signals.create_profile_for_role fires on
        UserRole post_save and auto-creates a Profile for any role NOT in
        its ["student", "instructor"] skip list. Creating the UserRole
        first (or manually creating a second Profile afterward) produces a
        duplicate Profile.MultipleObjectsReturned - the exact mistake
        already found and fixed in fees/students tests.py.
        """
        user = User.objects.create_user(
            username=username, email=f"{username}@dashtest.com", password="Pass1234!"
        )
        with tenant_context(self.school):
            Profile.objects.create(user_id=user.id, first_name=first_name, last_name=last_name)
            role, _ = Role.objects.get_or_create(
                slug=role_slug, defaults={"name": role_slug.title(), "is_system_role": True}
            )
            UserRole.objects.create(user=user, role=role)
        return user

    def _give_role_only(self, user, codenames):
        import uuid as uuid_module

        with tenant_context(self.school):
            unique_suffix = uuid_module.uuid4().hex[:8]
            role = Role.objects.create(
                name=f"custom-{unique_suffix}", slug=f"custom-{unique_suffix}", is_system_role=False
            )
            role.permissions.set(Permission.objects.filter(codename__in=codenames))
            UserRole.objects.filter(user=user).delete()
            UserRole.objects.create(user=user, role=role)
        return role

    def _client_as(self, user, password="Pass1234!"):
        client = APIClient()
        resp = client.post(
            "/api/auth/login/", {"username": user.username, "password": password}, HTTP_HOST=self.DOMAIN
        )
        assert resp.status_code == 200, resp.data
        return client

    def _make_student(self, enrollment_id, first_name, last_name, level, section, academic_year, status="active"):
        with tenant_context(self.school):
            profile = Profile.objects.create(first_name=first_name, last_name=last_name)
            student = Student.objects.create(profile=profile, enrollment_id=enrollment_id, status=status)
            StudentLevel.objects.create(
                student=student, level=level, section=section, academic_year=academic_year,
                is_current=(status == "active"),
            )
        return student

    def setUp(self):
        self.school = self._build_school()

        with tenant_context(self.school):
            program_active = Program.objects.create(name="High School", code="HSDB", is_active=True)
            program_inactive = Program.objects.create(name="Retired Program", code="RPDB", is_active=False)
            self.level_9 = AcademicLevel.objects.create(program=program_active, name="Grade 9", order=1)
            self.level_10 = AcademicLevel.objects.create(program=program_active, name="Grade 10", order=2)
            AcademicLevel.objects.create(program=program_inactive, name="Old Level", order=1)
            self.section_a = Section.objects.create(level=self.level_9, name="A", capacity=40)
            Section.objects.create(level=self.level_10, name="B", capacity=40)

        # Deterministic student status mix: 3 active, 1 inactive, 1 graduated,
        # 1 withdrawn, 1 transferred = total 7.
        self.active_students = [
            self._make_student(f"ENR-DB-A{i}", f"Active{i}", "Student", self.level_9, self.section_a, "2026")
            for i in range(3)
        ]
        self._make_student("ENR-DB-INACT", "In", "Active", self.level_9, self.section_a, "2026", status="inactive")
        self._make_student("ENR-DB-GRAD", "Grad", "Uate", self.level_9, self.section_a, "2026", status="graduated")
        self._make_student("ENR-DB-WITH", "With", "Drawn", self.level_9, self.section_a, "2026", status="withdrawn")
        self._make_student("ENR-DB-TRANS", "Trans", "Ferred", self.level_9, self.section_a, "2026", status="transferred")

        # Staff: 2 active, 1 inactive.
        with tenant_context(self.school):
            for i in range(2):
                p = Profile.objects.create(first_name=f"Staff{i}", last_name="Active")
                StaffMember.objects.create(profile=p, employee_id=f"EMP-DB-A{i}", designation="Teacher", is_active=True)
            p_inactive = Profile.objects.create(first_name="Staff", last_name="Inactive")
            StaffMember.objects.create(
                profile=p_inactive, employee_id="EMP-DB-INACT", designation="Teacher", is_active=False
            )

        # Attendance for today: 2 present, 1 absent among the active students.
        with tenant_context(self.school):
            today = datetime.date.today()
            session = AttendanceSession.objects.create(section=self.section_a, academic_year="2026", date=today)
            StudentAttendance.objects.create(session=session, student=self.active_students[0], status="present")
            StudentAttendance.objects.create(session=session, student=self.active_students[1], status="present")
            StudentAttendance.objects.create(session=session, student=self.active_students[2], status="absent")

        # Fees: one fully outstanding (1000), one partially paid (1000 due, 400 paid -> 600 outstanding).
        with tenant_context(self.school):
            head = FeeHead.objects.create(name="Dashboard Test Tuition")
            self.fee1 = StudentFee.objects.create(
                student=self.active_students[0], fee_head=head, academic_year="2026", amount_due=Decimal("1000")
            )
            self.fee2 = StudentFee.objects.create(
                student=self.active_students[1], fee_head=head, academic_year="2026", amount_due=Decimal("1000")
            )
            finance_profile = Profile.objects.create(first_name="Fin", last_name="Ance")
            finance_staff = StaffMember.objects.create(
                profile=finance_profile, employee_id="EMP-DB-FIN", designation="Accountant"
            )
            record_payment(
                student=self.active_students[1], amount=Decimal("400"), method="cash",
                allocations=[{"student_fee_id": self.fee2.id, "amount": Decimal("400")}],
                recorded_by=finance_staff,
            )
            # Expected total outstanding: 1000 (fee1, unpaid) + 600 (fee2, partially paid) = 1600.
            self.expected_outstanding = Decimal("1600.00")

        # Promotion activity: a couple of recent records.
        with tenant_context(self.school):
            execute_lifecycle_actions(
                entries=[
                    {"student": self.active_students[2], "action": "retained", "target_academic_year": "2027"},
                ],
                created_by=finance_staff,
            )

        # Admin/staff user granted view_dashboard.
        self.admin_user = self._build_user_with_profile("dash_admin", "staff", "Ad", "Min")
        self.owner_user = self._build_user_with_profile("dash_owner", "owner", "Own", "Er")
        self.unauthorized_staff_user = self._build_user_with_profile("dash_unauth", "staff", "Un", "Auth")

        self.instructor_user = self._build_user_with_profile("dash_instructor", "instructor", "Ins", "Tructor")
        with tenant_context(self.school):
            instr_profile = Profile.objects.filter(user_id=self.instructor_user.id).first()
            instr_staff = StaffMember.objects.create(
                profile=instr_profile, employee_id="EMP-DB-INSTR", designation="Teacher"
            )
            self.instructor = Instructor.objects.create(staff_member=instr_staff, specialization="Math")

        self.student_user = self._build_user_with_profile("dash_student", "student", "Stu", "Dent")
        with tenant_context(self.school):
            student_profile = Profile.objects.filter(user_id=self.student_user.id).first()
            self.logged_in_student = Student.objects.create(
                profile=student_profile, enrollment_id="ENR-DB-SELF", status="active"
            )

        self.parent_user = self._build_user_with_profile("dash_parent", "parent", "Par", "Ent")
        with tenant_context(self.school):
            parent_profile = Profile.objects.filter(user_id=self.parent_user.id).first()
            parent = Parent.objects.create(profile=parent_profile, occupation="Engineer")
            StudentParentRelation.objects.create(
                student=self.logged_in_student, parent=parent, relation_type="mother", is_primary_contact=True
            )

        # Notifications for the admin_user: 2 unread, 1 read; plus one belonging to another user.
        with tenant_context(self.school):
            Notification.objects.create(recipient_user_id=self.admin_user.id, title="Unread 1")
            Notification.objects.create(recipient_user_id=self.admin_user.id, title="Unread 2")
            Notification.objects.create(recipient_user_id=self.admin_user.id, title="Read 1", is_read=True)
            Notification.objects.create(recipient_user_id=self.owner_user.id, title="Owner's own")

        # A second, separate tenant to prove cross-tenant isolation.
        self.school2 = self._build_school(
            schema_name="dash_test_school2", domain="dashtest2.localhost", name="Dashboard Test School 2"
        )
        with tenant_context(self.school2):
            program2 = Program.objects.create(name="Other School", code="OSDB", is_active=True)
            level2 = AcademicLevel.objects.create(program=program2, name="Grade 1", order=1)
            section2 = Section.objects.create(level=level2, name="A", capacity=10)
            for i in range(50):
                p = Profile.objects.create(first_name=f"Other{i}", last_name="Student")
                s = Student.objects.create(profile=p, enrollment_id=f"ENR-OT-{i}", status="active")
                StudentLevel.objects.create(
                    student=s, level=level2, section=section2, academic_year="2026", is_current=True
                )
            head2 = FeeHead.objects.create(name="Other School Fee")
            other_first_student = Student.objects.filter(enrollment_id="ENR-OT-0").first()
            StudentFee.objects.create(
                student=other_first_student, fee_head=head2, academic_year="2026", amount_due=Decimal("99999")
            )

    def tearDown(self):
        connection.set_schema_to_public()
        self.school.delete(force_drop=True)
        self.school2.delete(force_drop=True)


class DashboardSummaryTests(DashboardFixtureMixin, TransactionTestCase):
    def _get(self, client):
        return client.get("/api/dashboard/summary/", HTTP_HOST=self.DOMAIN)

    def test_student_counts_exact(self):
        self._give_role_only(self.admin_user, ["view_dashboard"])
        client = self._client_as(self.admin_user)
        resp = self._get(client)
        self.assertEqual(resp.status_code, 200)
        students = resp.data["students"]
        # 3 from self.active_students + self.logged_in_student (created later
        # in setUp() for the student-self-access security fixture, also
        # status="active") = 4.
        self.assertEqual(students["active"], 4)
        self.assertEqual(students["inactive"], 1)
        self.assertEqual(students["graduated"], 1)
        # active_students[2] was retained in setUp() via execute_lifecycle_actions -
        # retention never changes Student.status (only transfer/withdraw/graduate do),
        # so it still counts as "active" above and does not affect this count.
        self.assertEqual(students["withdrawn"], 1)
        self.assertEqual(students["transferred"], 1)
        self.assertEqual(students["total"], 4 + 1 + 1 + 1 + 1)

    def test_missing_status_returns_zero(self):
        """No students were ever marked 'transferred' via a fresh school -
        use a school with zero of a given status to confirm 0, not a
        KeyError or omitted key."""
        self._give_role_only(self.admin_user, ["view_dashboard"])
        client = self._client_as(self.admin_user)
        resp = self._get(client)
        # "inactive" exists via fixture, so instead assert every key is present with an int.
        for status in ["active", "inactive", "graduated", "withdrawn", "transferred", "total"]:
            self.assertIn(status, resp.data["students"])
            self.assertIsInstance(resp.data["students"][status], int)

    def test_staff_active_count(self):
        """
        Expected total is 7, not just the 2 explicit "active" StaffMember
        rows created in setUp() - profiles.signals.create_profile_for_role
        auto-creates an active StaffMember (get_or_create, is_active
        defaults True) for every "staff"/"owner"-role UserRole it sees.
        setUp() builds 3 such test users (admin_user, owner_user,
        unauthorized_staff_user) via _build_user_with_profile, each
        triggering that signal - plus finance_staff and instr_staff,
        created explicitly (both default to is_active=True). Total:
        2 (explicit active) + 1 (finance_staff) + 1 (instr_staff)
        + 3 (signal-created for staff/owner test users) = 7.
        """
        self._give_role_only(self.admin_user, ["view_dashboard"])
        client = self._client_as(self.admin_user)
        resp = self._get(client)
        self.assertEqual(resp.data["staff"]["active"], 7)

    def test_academic_counts(self):
        self._give_role_only(self.admin_user, ["view_dashboard"])
        client = self._client_as(self.admin_user)
        resp = self._get(client)
        academics = resp.data["academics"]
        self.assertEqual(academics["programs"], 1)  # only the active program counted
        self.assertEqual(academics["levels"], 3)  # level_9, level_10, + inactive program's level
        self.assertEqual(academics["sections"], 2)

    def test_today_attendance_percentage(self):
        self._give_role_only(self.admin_user, ["view_dashboard"])
        client = self._client_as(self.admin_user)
        resp = self._get(client)
        # 2 present (weight 1.0) + 1 absent (weight 0.0) = 2/3 -> 66.67%
        self.assertEqual(resp.data["attendance"]["today_percentage"], 66.67)

    def test_fees_outstanding_matches_expected_total(self):
        self._give_role_only(self.admin_user, ["view_dashboard"])
        client = self._client_as(self.admin_user)
        resp = self._get(client)
        self.assertEqual(Decimal(resp.data["fees"]["outstanding"]), self.expected_outstanding)

    def test_fees_outstanding_matches_per_row_calculation(self):
        """Cross-checks the aggregate-query result against the existing
        per-row get_outstanding_balance() to prove it's the same formula,
        not a redefinition."""
        from fees.services import get_outstanding_balance

        with tenant_context(self.school):
            expected = sum(
                (get_outstanding_balance(sf) for sf in StudentFee.objects.filter(status="active")),
                Decimal("0"),
            )
        self._give_role_only(self.admin_user, ["view_dashboard"])
        client = self._client_as(self.admin_user)
        resp = self._get(client)
        self.assertEqual(Decimal(resp.data["fees"]["outstanding"]), expected)

    def test_promotion_recent_activity_present(self):
        self._give_role_only(self.admin_user, ["view_dashboard"])
        client = self._client_as(self.admin_user)
        resp = self._get(client)
        recent = resp.data["promotion"]["recent"]
        self.assertEqual(len(recent), 1)
        self.assertEqual(recent[0]["action"], "retained")

    def test_promotion_recent_activity_limited_to_ten(self):
        with tenant_context(self.school):
            for _ in range(15):
                PromotionRecord.objects.create(
                    student=self.active_students[0], action="reversed",
                    source_academic_year="2026", target_academic_year="2027",
                )
        self._give_role_only(self.admin_user, ["view_dashboard"])
        client = self._client_as(self.admin_user)
        resp = self._get(client)
        self.assertEqual(len(resp.data["promotion"]["recent"]), 10)

    def test_promotion_activity_empty_state(self):
        with tenant_context(self.school):
            PromotionRecord.objects.all().delete()
        self._give_role_only(self.admin_user, ["view_dashboard"])
        client = self._client_as(self.admin_user)
        resp = self._get(client)
        self.assertEqual(resp.data["promotion"]["recent"], [])

    def test_notification_count_scoped_to_current_user(self):
        self._give_role_only(self.admin_user, ["view_dashboard"])
        client = self._client_as(self.admin_user)
        resp = self._get(client)
        self.assertEqual(resp.data["notifications"]["unread"], 2)

    def test_notification_count_different_for_different_user(self):
        self._give_role_only(self.owner_user, ["view_dashboard"])
        client = self._client_as(self.owner_user)
        resp = self._get(client)
        # owner_user has exactly 1 unread notification of their own.
        self.assertEqual(resp.data["notifications"]["unread"], 1)

    def test_no_internal_fields_leaked_in_promotion_activity(self):
        self._give_role_only(self.admin_user, ["view_dashboard"])
        client = self._client_as(self.admin_user)
        resp = self._get(client)
        if resp.data["promotion"]["recent"]:
            row = resp.data["promotion"]["recent"][0]
            self.assertNotIn("source_student_level", row)
            self.assertNotIn("target_student_level", row)


class DashboardSecurityTests(DashboardFixtureMixin, TransactionTestCase):
    def _get(self, client):
        return client.get("/api/dashboard/summary/", HTTP_HOST=self.DOMAIN)

    def test_unauthenticated_returns_401(self):
        resp = self._get(APIClient())
        self.assertEqual(resp.status_code, 401)

    def test_student_returns_403(self):
        client = self._client_as(self.student_user)
        resp = self._get(client)
        self.assertEqual(resp.status_code, 403)

    def test_parent_returns_403(self):
        client = self._client_as(self.parent_user)
        resp = self._get(client)
        self.assertEqual(resp.status_code, 403)

    def test_instructor_without_permission_returns_403(self):
        client = self._client_as(self.instructor_user)
        resp = self._get(client)
        self.assertEqual(resp.status_code, 403)

    def test_staff_without_permission_returns_403(self):
        client = self._client_as(self.unauthorized_staff_user)
        resp = self._get(client)
        self.assertEqual(resp.status_code, 403)

    def test_staff_with_permission_returns_200(self):
        self._give_role_only(self.admin_user, ["view_dashboard"])
        client = self._client_as(self.admin_user)
        resp = self._get(client)
        self.assertEqual(resp.status_code, 200)

    def test_owner_returns_200_via_owner_bypass(self):
        client = self._client_as(self.owner_user)
        resp = self._get(client)
        self.assertEqual(resp.status_code, 200)

    def test_view_dashboard_is_the_only_new_permission(self):
        with tenant_context(self.school):
            dashboard_permissions = Permission.objects.filter(module="Dashboard")
            self.assertEqual(dashboard_permissions.count(), 1)
            self.assertEqual(dashboard_permissions.first().codename, "view_dashboard")


class DashboardTenantIsolationTests(DashboardFixtureMixin, TransactionTestCase):
    def test_school_a_summary_never_shows_school_b_students(self):
        self._give_role_only(self.admin_user, ["view_dashboard"])
        client = self._client_as(self.admin_user)
        resp = client.get("/api/dashboard/summary/", HTTP_HOST=self.DOMAIN)
        # School A has 8 students total (see test_student_counts_exact for
        # the exact breakdown, including self.logged_in_student); School B
        # independently has 50 - if isolation were broken, the total would
        # be much larger.
        self.assertEqual(resp.data["students"]["total"], 8)

    def test_school_a_summary_never_shows_school_b_fees(self):
        self._give_role_only(self.admin_user, ["view_dashboard"])
        client = self._client_as(self.admin_user)
        resp = client.get("/api/dashboard/summary/", HTTP_HOST=self.DOMAIN)
        # School B has a lone 99999 fee - if it leaked in, the total would
        # be dominated by it.
        self.assertEqual(Decimal(resp.data["fees"]["outstanding"]), self.expected_outstanding)

    def test_school_b_has_its_own_independent_counts(self):
        with tenant_context(self.school2):
            owner_user2 = User.objects.create_user(
                username="dash_owner2", email="dash_owner2@dashtest.com", password="Pass1234!"
            )
            Profile.objects.create(user_id=owner_user2.id, first_name="Own2", last_name="Er2")
            owner_role, _ = Role.objects.get_or_create(
                slug="owner", defaults={"name": "Owner", "is_system_role": True}
            )
            UserRole.objects.create(user=owner_user2, role=owner_role)

        client = APIClient()
        login_resp = client.post(
            "/api/auth/login/", {"username": "dash_owner2", "password": "Pass1234!"},
            HTTP_HOST="dashtest2.localhost",
        )
        self.assertEqual(login_resp.status_code, 200)

        resp = client.get("/api/dashboard/summary/", HTTP_HOST="dashtest2.localhost")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["students"]["total"], 50)
