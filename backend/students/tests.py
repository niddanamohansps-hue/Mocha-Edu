import uuid as uuid_module
from decimal import Decimal

from django.db import IntegrityError, connection, transaction
from django.test import TransactionTestCase
from django_tenants.utils import tenant_context
from rest_framework.test import APIClient

from academics.models import AcademicLevel, Program, Section
from accounts.models import User
from core.models import AuditLog
from families.models import Parent, StudentParentRelation
from organizations.models import Domain, Organization
from profiles.models import Profile
from roles.models import Permission, Role, UserRole
from staff.models import Instructor, StaffMember

from .models import PromotionRecord, Student, StudentLevel
from .services import (
    execute_lifecycle_actions,
    get_next_level,
    preview_lifecycle_actions,
    reverse_promotion,
    validate_academic_year,
)


class PromotionFixtureMixin:
    """Mirrors fees/parent_portal/examinations tests.py exactly."""

    SCHEMA_NAME = "promo_test_school"
    DOMAIN = "promotest.localhost"

    def _build_school(self, schema_name=None, domain=None, name="Promotion Test School"):
        schema_name = schema_name or self.SCHEMA_NAME
        domain = domain or self.DOMAIN
        connection.set_schema_to_public()
        school = Organization.objects.create(schema_name=schema_name, name=name)
        Domain.objects.create(domain=domain, tenant=school, is_primary=True)
        return school

    def _build_user(self, username, role_slug):
        user = User.objects.create_user(
            username=username, email=f"{username}@promotest.com", password="Pass1234!"
        )
        with tenant_context(self.school):
            role, _ = Role.objects.get_or_create(
                slug=role_slug, defaults={"name": role_slug.title(), "is_system_role": True}
            )
            UserRole.objects.create(user=user, role=role)
        return user

    def _give_role_only(self, user, codenames):
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

    def _make_student(self, enrollment_id, first_name, last_name, level, section, academic_year, status="active", user=None):
        with tenant_context(self.school):
            profile = Profile.objects.create(
                user_id=user.id if user else None, first_name=first_name, last_name=last_name
            )
            student = Student.objects.create(
                profile=profile, enrollment_id=enrollment_id, status=status
            )
            StudentLevel.objects.create(
                student=student, level=level, section=section, academic_year=academic_year, is_current=True
            )
            if user:
                student_role, _ = Role.objects.get_or_create(
                    slug="student", defaults={"name": "Student", "is_system_role": True}
                )
                UserRole.objects.create(user=user, role=student_role)
        return student

    def _make_parent(self, username, first_name, last_name):
        user = User.objects.create_user(
            username=username, email=f"{username}@promotest.com", password="Pass1234!"
        )
        with tenant_context(self.school):
            profile = Profile.objects.create(user_id=user.id, first_name=first_name, last_name=last_name)
            parent = Parent.objects.create(profile=profile, occupation="Engineer")
            parent_role, _ = Role.objects.get_or_create(
                slug="parent", defaults={"name": "Parent", "is_system_role": True}
            )
            UserRole.objects.create(user=user, role=parent_role)
        return user, parent

    def setUp(self):
        self.school = self._build_school()

        with tenant_context(self.school):
            program = Program.objects.create(name="High School", code="HSPR")
            self.level_9 = AcademicLevel.objects.create(program=program, name="Grade 9", order=1)
            self.level_10 = AcademicLevel.objects.create(program=program, name="Grade 10", order=2)
            self.level_11 = AcademicLevel.objects.create(program=program, name="Grade 11", order=3)
            self.section_9a = Section.objects.create(level=self.level_9, name="A", capacity=40)
            self.section_10a = Section.objects.create(level=self.level_10, name="A", capacity=40)
            self.section_10b = Section.objects.create(level=self.level_10, name="B", capacity=40)

        self.student1 = self._make_student("ENR-PR-1", "Sam", "Pupil", self.level_9, self.section_9a, "2026")
        self.student2 = self._make_student("ENR-PR-2", "Alex", "Second", self.level_9, self.section_9a, "2026")
        self.student3 = self._make_student("ENR-PR-3", "Otto", "Other", self.level_9, self.section_9a, "2026")
        self.final_student = self._make_student("ENR-PR-FIN", "Grad", "Uate", self.level_11, None, "2026")
        self.inactive_student = self._make_student(
            "ENR-PR-INACT", "In", "Active", self.level_9, self.section_9a, "2026", status="inactive"
        )

        # Staff member with an instructor record (auth test target)
        self.instructor_user = self._build_user("pr_instructor", "instructor")
        with tenant_context(self.school):
            instr_profile = Profile.objects.create(
                user_id=self.instructor_user.id, first_name="Ivy", last_name="Teach"
            )
            instr_staff = StaffMember.objects.create(
                profile=instr_profile, employee_id="EMP-PR-1", designation="Teacher"
            )
            self.instructor = Instructor.objects.create(staff_member=instr_staff, specialization="Math")

        # Admin/finance-style staff who will be granted manage_student_promotion per
        # test. Built directly (not via _build_user) so the Profile can be linked
        # BEFORE the UserRole is created - profiles.signals.create_profile_for_role
        # fires on UserRole post_save and auto-creates a Profile for any role NOT
        # in its ["student", "instructor"] skip list. "staff" is not skip-listed,
        # so building via _build_user first and creating a real Profile afterward
        # would leave two Profile rows for the same user_id (the exact bug already
        # found and fixed in fees/tests.py's finance_user fixture).
        self.admin_user = User.objects.create_user(
            username="pr_admin", email="pr_admin@promotest.com", password="Pass1234!"
        )
        with tenant_context(self.school):
            admin_profile = Profile.objects.create(
                user_id=self.admin_user.id, first_name="Ad", last_name="Min"
            )
            self.admin_staff_member = StaffMember.objects.create(
                profile=admin_profile, employee_id="EMP-PR-ADMIN", designation="Registrar"
            )
            staff_role, _ = Role.objects.get_or_create(
                slug="staff", defaults={"name": "Staff", "is_system_role": True}
            )
            UserRole.objects.create(user=self.admin_user, role=staff_role)

        self.owner_user = self._build_user("pr_owner", "owner")
        self.random_staff_user = self._build_user("pr_random", "staff")

        # Parent linked to student1
        self.parent_user, self.parent = self._make_parent("pr_parent", "Pat", "Guardian")
        with tenant_context(self.school):
            StudentParentRelation.objects.create(
                student=self.student1, parent=self.parent, relation_type="mother", is_primary_contact=True
            )

        # A logged-in student account (for "student account" security tests)
        self.student_login_user = User.objects.create_user(
            username="pr_student_self", email="pr_student_self@promotest.com", password="Pass1234!"
        )
        with tenant_context(self.school):
            self.student1.profile.user_id = self.student_login_user.id
            self.student1.profile.save()
            student_role, _ = Role.objects.get_or_create(
                slug="student", defaults={"name": "Student", "is_system_role": True}
            )
            UserRole.objects.create(user=self.student_login_user, role=student_role)

        # A second, separate tenant to prove cross-tenant isolation.
        self.school2 = self._build_school(
            schema_name="promo_test_school2", domain="promotest2.localhost", name="Promotion Test School 2"
        )
        with tenant_context(self.school2):
            program2 = Program.objects.create(name="Other School", code="OSPR")
            level2 = AcademicLevel.objects.create(program=program2, name="Grade 1", order=1)
            section2 = Section.objects.create(level=level2, name="A", capacity=10)
            profile2 = Profile.objects.create(first_name="Cross", last_name="Tenant")
            self.other_tenant_student = Student.objects.create(
                profile=profile2, enrollment_id="ENR-OT-1", status="active"
            )
            StudentLevel.objects.create(
                student=self.other_tenant_student, level=level2, section=section2,
                academic_year="2026", is_current=True,
            )

    def tearDown(self):
        connection.set_schema_to_public()
        self.school.delete(force_drop=True)
        self.school2.delete(force_drop=True)

    def _promote_entry(self, student, action="promoted", target_year="2027", target_level=None, target_section=None, reason=""):
        entry = {"student": student, "action": action, "target_academic_year": target_year, "reason": reason}
        if target_level is not None:
            entry["target_level_obj"] = target_level
        if target_section is not None:
            entry["target_section_obj"] = target_section
        return entry

    def _execute(self, entries):
        with tenant_context(self.school):
            return execute_lifecycle_actions(entries=entries, created_by=self.admin_staff_member)

    def _api_entries(self, students, action="promoted", target_year="2027", target_level_id=None, target_section_id=None):
        entries = []
        for s in students:
            e = {"student": str(s.id), "action": action, "target_academic_year": target_year}
            if target_level_id:
                e["target_level"] = str(target_level_id)
            if target_section_id:
                e["target_section"] = str(target_section_id)
            entries.append(e)
        return entries


class PromotionModelTests(PromotionFixtureMixin, TransactionTestCase):
    def test_promotion_record_created(self):
        with tenant_context(self.school):
            record = PromotionRecord.objects.create(
                student=self.student1, action="promoted",
                source_academic_year="2026", target_academic_year="2027",
            )
            self.assertEqual(PromotionRecord.objects.count(), 1)
            self.assertEqual(record.action, "promoted")

    def test_action_choices_enforced_at_form_level(self):
        with tenant_context(self.school):
            valid_actions = {c[0] for c in PromotionRecord._meta.get_field("action").choices}
            self.assertEqual(
                valid_actions,
                {"promoted", "retained", "transferred", "withdrawn", "graduated", "reversed"},
            )

    def test_student_status_supports_transferred(self):
        with tenant_context(self.school):
            valid_statuses = {c[0] for c in Student._meta.get_field("status").choices}
            self.assertIn("transferred", valid_statuses)
            self.assertEqual(
                valid_statuses, {"active", "inactive", "graduated", "withdrawn", "transferred"}
            )

    def test_studentlevel_unique_together_still_enforced(self):
        with tenant_context(self.school):
            with self.assertRaises(IntegrityError):
                with transaction.atomic():
                    StudentLevel.objects.create(
                        student=self.student1, level=self.level_9, academic_year="2026", is_current=True
                    )

    def test_current_studentlevel_correctness_after_promotion(self):
        self._execute([self._promote_entry(self.student1)])
        with tenant_context(self.school):
            current_rows = StudentLevel.objects.filter(student=self.student1, is_current=True)
            self.assertEqual(current_rows.count(), 1)
            self.assertEqual(current_rows.first().academic_year, "2027")
            old_row = StudentLevel.objects.get(student=self.student1, academic_year="2026")
            self.assertFalse(old_row.is_current)

    def test_promotion_record_not_deleted_by_anything_in_this_module(self):
        self._execute([self._promote_entry(self.student1)])
        with tenant_context(self.school):
            self.assertEqual(PromotionRecord.objects.filter(student=self.student1).count(), 1)


class PromotionExecutionTests(PromotionFixtureMixin, TransactionTestCase):
    def test_single_student_promotion(self):
        results = self._execute([self._promote_entry(self.student1)])
        self.assertEqual(results[0]["status"], "success")
        self.assertEqual(results[0]["action"], "promoted")

    def test_whole_section_promotion(self):
        entries = [self._promote_entry(s) for s in [self.student1, self.student2, self.student3]]
        results = self._execute(entries)
        self.assertTrue(all(r["status"] == "success" for r in results))
        with tenant_context(self.school):
            for s in [self.student1, self.student2, self.student3]:
                self.assertTrue(
                    StudentLevel.objects.filter(student=s, academic_year="2027", is_current=True).exists()
                )

    def test_deselected_student_not_included(self):
        entries = [self._promote_entry(self.student1)]  # student2/student3 deliberately excluded
        self._execute(entries)
        with tenant_context(self.school):
            self.assertFalse(StudentLevel.objects.filter(student=self.student2, academic_year="2027").exists())

    def test_mixed_actions_in_one_batch(self):
        entries = [
            self._promote_entry(self.student1, action="promoted"),
            self._promote_entry(self.student2, action="retained"),
            self._promote_entry(self.student3, action="withdrawn", target_year=""),
        ]
        results = self._execute(entries)
        by_student = {r["student"]: r for r in results}
        self.assertEqual(by_student[str(self.student1.id)]["status"], "success")
        self.assertEqual(by_student[str(self.student2.id)]["status"], "success")
        self.assertEqual(by_student[str(self.student3.id)]["status"], "success")
        with tenant_context(self.school):
            self.student3.refresh_from_db()
            self.assertEqual(self.student3.status, "withdrawn")

    def test_explicit_target_level_override(self):
        results = self._execute([self._promote_entry(self.student1, target_level=self.level_11)])
        self.assertEqual(results[0]["status"], "success")
        with tenant_context(self.school):
            row = StudentLevel.objects.get(student=self.student1, academic_year="2027")
            self.assertEqual(row.level_id, self.level_11.id)

    def test_explicit_target_section(self):
        results = self._execute(
            [self._promote_entry(self.student1, target_level=self.level_10, target_section=self.section_10b)]
        )
        self.assertEqual(results[0]["status"], "success")
        with tenant_context(self.school):
            row = StudentLevel.objects.get(student=self.student1, academic_year="2027")
            self.assertEqual(row.section_id, self.section_10b.id)

    def test_default_next_level_used_when_not_specified(self):
        results = self._execute([self._promote_entry(self.student1)])
        self.assertEqual(results[0]["status"], "success")
        with tenant_context(self.school):
            row = StudentLevel.objects.get(student=self.student1, academic_year="2027")
            self.assertEqual(row.level_id, self.level_10.id)  # order 2, next after level_9's order 1


class RetentionTests(PromotionFixtureMixin, TransactionTestCase):
    def test_retention_keeps_same_level(self):
        results = self._execute([self._promote_entry(self.student1, action="retained")])
        self.assertEqual(results[0]["status"], "success")
        with tenant_context(self.school):
            row = StudentLevel.objects.get(student=self.student1, academic_year="2027")
            self.assertEqual(row.level_id, self.level_9.id)

    def test_retention_requires_different_target_year(self):
        results = self._execute([self._promote_entry(self.student1, action="retained", target_year="2026")])
        self.assertEqual(results[0]["status"], "skipped")


class TransferTests(PromotionFixtureMixin, TransactionTestCase):
    def test_transfer_sets_status(self):
        results = self._execute([self._promote_entry(self.student1, action="transferred", target_year="")])
        self.assertEqual(results[0]["status"], "success")
        with tenant_context(self.school):
            self.student1.refresh_from_db()
            self.assertEqual(self.student1.status, "transferred")

    def test_transfer_closes_current_studentlevel(self):
        self._execute([self._promote_entry(self.student1, action="transferred", target_year="")])
        with tenant_context(self.school):
            row = StudentLevel.objects.get(student=self.student1, academic_year="2026")
            self.assertFalse(row.is_current)

    def test_transfer_creates_no_new_studentlevel(self):
        self._execute([self._promote_entry(self.student1, action="transferred", target_year="")])
        with tenant_context(self.school):
            self.assertEqual(StudentLevel.objects.filter(student=self.student1).count(), 1)


class WithdrawalTests(PromotionFixtureMixin, TransactionTestCase):
    def test_withdrawal_sets_status(self):
        results = self._execute([self._promote_entry(self.student1, action="withdrawn", target_year="")])
        self.assertEqual(results[0]["status"], "success")
        with tenant_context(self.school):
            self.student1.refresh_from_db()
            self.assertEqual(self.student1.status, "withdrawn")

    def test_withdrawal_closes_current_studentlevel(self):
        self._execute([self._promote_entry(self.student1, action="withdrawn", target_year="")])
        with tenant_context(self.school):
            row = StudentLevel.objects.get(student=self.student1, academic_year="2026")
            self.assertFalse(row.is_current)


class GraduationTests(PromotionFixtureMixin, TransactionTestCase):
    def test_graduation_sets_status(self):
        results = self._execute([self._promote_entry(self.final_student, action="graduated", target_year="")])
        self.assertEqual(results[0]["status"], "success")
        with tenant_context(self.school):
            self.final_student.refresh_from_db()
            self.assertEqual(self.final_student.status, "graduated")

    def test_graduation_closes_current_studentlevel(self):
        self._execute([self._promote_entry(self.final_student, action="graduated", target_year="")])
        with tenant_context(self.school):
            row = StudentLevel.objects.get(student=self.final_student, academic_year="2026")
            self.assertFalse(row.is_current)

    def test_graduation_not_automatic_from_level_order(self):
        """Reaching the highest-order level must never auto-graduate a
        student - graduation is always an explicit admin action."""
        with tenant_context(self.school):
            self.assertEqual(self.final_student.status, "active")
            self.assertIsNone(get_next_level(self.level_11))


class WarningTests(PromotionFixtureMixin, TransactionTestCase):
    def test_outstanding_fee_warning_shown(self):
        with tenant_context(self.school):
            from fees.models import FeeHead, StudentFee

            head = FeeHead.objects.create(name="PromoTest Tuition")
            StudentFee.objects.create(
                student=self.student1, fee_head=head, academic_year="2026", amount_due=Decimal("500")
            )
            results = preview_lifecycle_actions(entries=[self._promote_entry(self.student1)])
        self.assertTrue(any("Outstanding fees" in w for w in results[0]["warnings"]))

    def test_failed_exam_warning_shown(self):
        with tenant_context(self.school):
            from examinations.models import ExamResult, Examination, ExamType

            exam_type = ExamType.objects.create(name="Annual", order=1)
            import datetime

            examination = Examination.objects.create(
                academic_year="2026", name="Annual 2026", exam_type=exam_type,
                start_date=datetime.date(2026, 3, 1), end_date=datetime.date(2026, 3, 10),
            )
            ExamResult.objects.create(
                examination=examination, student=self.student1, academic_year="2026",
                total_marks_obtained=Decimal("20"), total_max_marks=Decimal("100"),
                percentage=Decimal("20"), overall_grade="F", is_pass=False, subject_breakdown=[],
            )
            results = preview_lifecycle_actions(entries=[self._promote_entry(self.student1)])
        self.assertTrue(any("Failed examination" in w for w in results[0]["warnings"]))

    def test_warnings_do_not_block_execution(self):
        with tenant_context(self.school):
            from fees.models import FeeHead, StudentFee

            head = FeeHead.objects.create(name="PromoTest Tuition 2")
            StudentFee.objects.create(
                student=self.student1, fee_head=head, academic_year="2026", amount_due=Decimal("500")
            )
        results = self._execute([self._promote_entry(self.student1)])
        self.assertEqual(results[0]["status"], "success")


class FailureCaseTests(PromotionFixtureMixin, TransactionTestCase):
    def test_duplicate_target_year_rejected(self):
        with tenant_context(self.school):
            StudentLevel.objects.create(
                student=self.student1, level=self.level_10, academic_year="2027", is_current=False
            )
        results = self._execute([self._promote_entry(self.student1)])
        self.assertEqual(results[0]["status"], "skipped")
        self.assertIn("already exists", results[0]["error"])

    def test_invalid_level_reported_not_500(self):
        self._give_role_only(self.admin_user, ["manage_student_promotion"])
        client = self._client_as(self.admin_user)
        resp = client.post(
            "/api/students/promotion/execute/",
            {
                "source_academic_year": "2026",
                "entries": [
                    {
                        "student": str(self.student1.id), "action": "promoted",
                        "target_academic_year": "2027",
                        "target_level": str(uuid_module.uuid4()),
                    }
                ],
            },
            HTTP_HOST=self.DOMAIN, format="json",
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["results"][0]["status"], "skipped")

    def test_invalid_section_reported_not_500(self):
        self._give_role_only(self.admin_user, ["manage_student_promotion"])
        client = self._client_as(self.admin_user)
        resp = client.post(
            "/api/students/promotion/execute/",
            {
                "source_academic_year": "2026",
                "entries": [
                    {
                        "student": str(self.student1.id), "action": "promoted",
                        "target_academic_year": "2027",
                        "target_section": str(uuid_module.uuid4()),
                    }
                ],
            },
            HTTP_HOST=self.DOMAIN, format="json",
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["results"][0]["status"], "skipped")

    def test_missing_target_year_rejected(self):
        results = self._execute([self._promote_entry(self.student1, target_year="")])
        self.assertEqual(results[0]["status"], "skipped")

    def test_inactive_student_excluded_from_candidates(self):
        with tenant_context(self.school):
            from .services import get_promotion_candidates

            candidates = get_promotion_candidates("2026", self.level_9.id)
            student_ids = {row.student_id for row in candidates}
            self.assertNotIn(self.inactive_student.id, student_ids)

    def test_inactive_student_rejected_on_execute(self):
        results = self._execute([self._promote_entry(self.inactive_student)])
        self.assertEqual(results[0]["status"], "skipped")

    def test_withdrawn_student_cannot_be_promoted_again(self):
        self._execute([self._promote_entry(self.student1, action="withdrawn", target_year="")])
        results = self._execute([self._promote_entry(self.student1)])
        self.assertEqual(results[0]["status"], "skipped")

    def test_graduated_student_cannot_be_promoted_again(self):
        self._execute([self._promote_entry(self.final_student, action="graduated", target_year="")])
        results = self._execute([self._promote_entry(self.final_student)])
        self.assertEqual(results[0]["status"], "skipped")

    def test_transferred_student_cannot_be_promoted_again(self):
        self._execute([self._promote_entry(self.student1, action="transferred", target_year="")])
        results = self._execute([self._promote_entry(self.student1)])
        self.assertEqual(results[0]["status"], "skipped")

    def test_malformed_academic_year_rejected(self):
        with tenant_context(self.school):
            with self.assertRaises(Exception):
                validate_academic_year("")

    def test_one_bad_student_does_not_abort_whole_batch(self):
        with tenant_context(self.school):
            StudentLevel.objects.create(
                student=self.student2, level=self.level_10, academic_year="2027", is_current=False
            )
        entries = [self._promote_entry(self.student1), self._promote_entry(self.student2)]
        results = self._execute(entries)
        by_student = {r["student"]: r for r in results}
        self.assertEqual(by_student[str(self.student1.id)]["status"], "success")
        self.assertEqual(by_student[str(self.student2.id)]["status"], "skipped")


class SecurityTests(PromotionFixtureMixin, TransactionTestCase):
    def _candidates(self, client):
        return client.get(
            f"/api/students/promotion/candidates/?academic_year=2026&level={self.level_9.id}",
            HTTP_HOST=self.DOMAIN,
        )

    def test_unauthenticated_denied(self):
        resp = self._candidates(APIClient())
        self.assertIn(resp.status_code, (401, 403))

    def test_no_permission_denied(self):
        client = self._client_as(self.random_staff_user)
        resp = self._candidates(client)
        self.assertEqual(resp.status_code, 403)

    def test_student_account_denied(self):
        client = self._client_as(self.student_login_user)
        resp = self._candidates(client)
        self.assertEqual(resp.status_code, 403)

    def test_parent_account_denied(self):
        client = self._client_as(self.parent_user)
        resp = self._candidates(client)
        self.assertEqual(resp.status_code, 403)

    def test_instructor_account_denied(self):
        client = self._client_as(self.instructor_user)
        resp = self._candidates(client)
        self.assertEqual(resp.status_code, 403)

    def test_unrelated_staff_role_denied(self):
        self._give_role_only(self.random_staff_user, ["view_student"])
        client = self._client_as(self.random_staff_user)
        resp = self._candidates(client)
        self.assertEqual(resp.status_code, 403)

    def test_authorized_administrator_allowed(self):
        self._give_role_only(self.admin_user, ["manage_student_promotion"])
        client = self._client_as(self.admin_user)
        resp = self._candidates(client)
        self.assertEqual(resp.status_code, 200)

    def test_owner_allowed(self):
        client = self._client_as(self.owner_user)
        resp = self._candidates(client)
        self.assertEqual(resp.status_code, 200)

    def test_cross_tenant_student_not_promotable(self):
        self._give_role_only(self.admin_user, ["manage_student_promotion"])
        client = self._client_as(self.admin_user)
        resp = client.post(
            "/api/students/promotion/execute/",
            {
                "source_academic_year": "2026",
                "entries": [
                    {
                        "student": str(self.other_tenant_student.id), "action": "promoted",
                        "target_academic_year": "2027",
                    }
                ],
            },
            HTTP_HOST=self.DOMAIN, format="json",
        )
        self.assertEqual(resp.data["results"][0]["status"], "skipped")

    def test_nonexistent_student_reported_cleanly(self):
        self._give_role_only(self.admin_user, ["manage_student_promotion"])
        client = self._client_as(self.admin_user)
        resp = client.post(
            "/api/students/promotion/execute/",
            {
                "source_academic_year": "2026",
                "entries": [
                    {
                        "student": str(uuid_module.uuid4()), "action": "promoted",
                        "target_academic_year": "2027",
                    }
                ],
            },
            HTTP_HOST=self.DOMAIN, format="json",
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["results"][0]["status"], "skipped")

    def test_no_self_access_endpoint_exists_for_students(self):
        """Promotion is purely administrative - even the student's own
        account must never be authorized, unlike Attendance/Examinations."""
        client = self._client_as(self.student_login_user)
        resp = client.get(
            f"/api/students/promotion/history/?student={self.student1.id}", HTTP_HOST=self.DOMAIN
        )
        self.assertEqual(resp.status_code, 403)


class ConcurrencyTests(PromotionFixtureMixin, TransactionTestCase):
    def test_duplicate_concurrent_promotion_second_call_rejected(self):
        """Simulates two sequential promotion attempts on the same student
        for the same target year - the second must be rejected, not create
        a second is_current row (the select_for_update + unique_together
        combination is what actually prevents a true concurrent race; this
        proves the same-process sequential case, which already exercises
        the duplicate-target-year guard identically)."""
        first = self._execute([self._promote_entry(self.student1)])
        self.assertEqual(first[0]["status"], "success")
        second = self._execute([self._promote_entry(self.student1)])
        self.assertEqual(second[0]["status"], "skipped")

        with tenant_context(self.school):
            self.assertEqual(
                StudentLevel.objects.filter(student=self.student1, is_current=True).count(), 1
            )


class AuditTests(PromotionFixtureMixin, TransactionTestCase):
    def _execute_via_api(self, entries, source_year="2026"):
        self._give_role_only(self.admin_user, ["manage_student_promotion"])
        client = self._client_as(self.admin_user)
        return client.post(
            "/api/students/promotion/execute/",
            {"source_academic_year": source_year, "entries": entries},
            HTTP_HOST=self.DOMAIN, format="json",
        )

    def test_one_audit_event_per_action_group(self):
        entries = self._api_entries([self.student1], action="promoted") + self._api_entries(
            [self.student3], action="withdrawn", target_year=""
        )
        self._execute_via_api(entries)
        with tenant_context(self.school):
            self.assertTrue(AuditLog.objects.filter(action="student_promoted").exists())
            self.assertTrue(AuditLog.objects.filter(action="student_withdrawn").exists())

    def test_audit_metadata_has_correct_student_count(self):
        entries = self._api_entries([self.student1, self.student2], action="promoted")
        self._execute_via_api(entries)
        with tenant_context(self.school):
            log = AuditLog.objects.filter(action="student_promoted").first()
            self.assertEqual(log.changes["student_count"], 2)

    def test_reversal_audit_logged(self):
        self._give_role_only(self.admin_user, ["manage_student_promotion"])
        client = self._client_as(self.admin_user)
        exec_resp = self._execute_via_api(self._api_entries([self.student1], action="promoted"))
        record_id = exec_resp.data["results"][0]["record_id"]

        client.post(f"/api/students/promotion/{record_id}/reverse/", {}, HTTP_HOST=self.DOMAIN)
        with tenant_context(self.school):
            self.assertTrue(AuditLog.objects.filter(action="promotion_reversed").exists())

    def test_no_audit_event_when_batch_is_entirely_skipped(self):
        with tenant_context(self.school):
            StudentLevel.objects.create(
                student=self.student1, level=self.level_10, academic_year="2027", is_current=False
            )
        self._execute_via_api(self._api_entries([self.student1], action="promoted"))
        with tenant_context(self.school):
            self.assertFalse(AuditLog.objects.filter(action="student_promoted").exists())


class ReversalTests(PromotionFixtureMixin, TransactionTestCase):
    def test_promotion_can_be_reversed(self):
        with tenant_context(self.school):
            record = execute_lifecycle_actions(
                entries=[self._promote_entry(self.student1)], created_by=self.admin_staff_member
            )
            reversal = reverse_promotion(
                record=PromotionRecord.objects.get(id=record[0]["record_id"]), created_by=self.admin_staff_member
            )
            self.assertEqual(reversal.action, "reversed")

    def test_history_remains_after_reversal(self):
        with tenant_context(self.school):
            result = execute_lifecycle_actions(
                entries=[self._promote_entry(self.student1)], created_by=self.admin_staff_member
            )
            original = PromotionRecord.objects.get(id=result[0]["record_id"])
            reverse_promotion(record=original, created_by=self.admin_staff_member)
            original.refresh_from_db()
            self.assertTrue(PromotionRecord.objects.filter(id=original.id).exists())
            self.assertEqual(PromotionRecord.objects.filter(student=self.student1).count(), 2)

    def test_previous_current_level_restored(self):
        with tenant_context(self.school):
            result = execute_lifecycle_actions(
                entries=[self._promote_entry(self.student1)], created_by=self.admin_staff_member
            )
            original = PromotionRecord.objects.get(id=result[0]["record_id"])
            reverse_promotion(record=original, created_by=self.admin_staff_member)

            old_row = StudentLevel.objects.get(student=self.student1, academic_year="2026")
            new_row = StudentLevel.objects.get(student=self.student1, academic_year="2027")
            self.assertTrue(old_row.is_current)
            self.assertFalse(new_row.is_current)

    def test_reversed_record_created(self):
        with tenant_context(self.school):
            result = execute_lifecycle_actions(
                entries=[self._promote_entry(self.student1)], created_by=self.admin_staff_member
            )
            original = PromotionRecord.objects.get(id=result[0]["record_id"])
            reversal = reverse_promotion(record=original, created_by=self.admin_staff_member)
            self.assertEqual(reversal.reverses_id, original.id)

    def test_invalid_reversal_rejected_when_already_reversed(self):
        with tenant_context(self.school):
            result = execute_lifecycle_actions(
                entries=[self._promote_entry(self.student1)], created_by=self.admin_staff_member
            )
            original = PromotionRecord.objects.get(id=result[0]["record_id"])
            reverse_promotion(record=original, created_by=self.admin_staff_member)

            from rest_framework.exceptions import ValidationError as DRFValidationError

            with self.assertRaises(DRFValidationError):
                reverse_promotion(record=original, created_by=self.admin_staff_member)

    def test_invalid_reversal_rejected_when_state_changed(self):
        with tenant_context(self.school):
            result = execute_lifecycle_actions(
                entries=[self._promote_entry(self.student1)], created_by=self.admin_staff_member
            )
            original = PromotionRecord.objects.get(id=result[0]["record_id"])
            # Student is promoted again from the 2027 row before anyone tries to reverse the first promotion.
            execute_lifecycle_actions(
                entries=[self._promote_entry(self.student1, target_year="2028")],
                created_by=self.admin_staff_member,
            )

            from rest_framework.exceptions import ValidationError as DRFValidationError

            with self.assertRaises(DRFValidationError):
                reverse_promotion(record=original, created_by=self.admin_staff_member)

    def test_reversal_of_terminal_action_rejected(self):
        with tenant_context(self.school):
            result = execute_lifecycle_actions(
                entries=[self._promote_entry(self.student1, action="withdrawn", target_year="")],
                created_by=self.admin_staff_member,
            )
            record = PromotionRecord.objects.get(id=result[0]["record_id"])

            from rest_framework.exceptions import ValidationError as DRFValidationError

            with self.assertRaises(DRFValidationError):
                reverse_promotion(record=record, created_by=self.admin_staff_member)

    def test_reverse_endpoint_requires_permission(self):
        with tenant_context(self.school):
            result = execute_lifecycle_actions(
                entries=[self._promote_entry(self.student1)], created_by=self.admin_staff_member
            )
            record_id = result[0]["record_id"]
        client = self._client_as(self.random_staff_user)
        resp = client.post(f"/api/students/promotion/{record_id}/reverse/", {}, HTTP_HOST=self.DOMAIN)
        self.assertEqual(resp.status_code, 403)


class PreviewEndpointTests(PromotionFixtureMixin, TransactionTestCase):
    def test_preview_performs_no_writes(self):
        self._give_role_only(self.admin_user, ["manage_student_promotion"])
        client = self._client_as(self.admin_user)
        resp = client.post(
            "/api/students/promotion/preview/",
            {"source_academic_year": "2026", "entries": self._api_entries([self.student1])},
            HTTP_HOST=self.DOMAIN, format="json",
        )
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.data[0]["eligible"])
        with tenant_context(self.school):
            self.assertFalse(StudentLevel.objects.filter(student=self.student1, academic_year="2027").exists())

    def test_preview_surfaces_conflict(self):
        with tenant_context(self.school):
            StudentLevel.objects.create(
                student=self.student1, level=self.level_10, academic_year="2027", is_current=False
            )
        self._give_role_only(self.admin_user, ["manage_student_promotion"])
        client = self._client_as(self.admin_user)
        resp = client.post(
            "/api/students/promotion/preview/",
            {"source_academic_year": "2026", "entries": self._api_entries([self.student1])},
            HTTP_HOST=self.DOMAIN, format="json",
        )
        self.assertFalse(resp.data[0]["eligible"])


class HistoryEndpointTests(PromotionFixtureMixin, TransactionTestCase):
    def test_history_filters_by_student(self):
        with tenant_context(self.school):
            execute_lifecycle_actions(
                entries=[self._promote_entry(self.student1), self._promote_entry(self.student2)],
                created_by=self.admin_staff_member,
            )
        self._give_role_only(self.admin_user, ["manage_student_promotion"])
        client = self._client_as(self.admin_user)
        resp = client.get(
            f"/api/students/promotion/history/?student={self.student1.id}", HTTP_HOST=self.DOMAIN
        )
        self.assertEqual(len(resp.data), 1)
        # PromotionRecordSerializer's "student" is a ModelSerializer FK
        # field, so resp.data holds the raw UUID (not yet JSON-rendered to
        # a string) - compare UUID to UUID, not UUID to str.
        self.assertEqual(resp.data[0]["student"], self.student1.id)

    def test_history_filters_by_action(self):
        with tenant_context(self.school):
            execute_lifecycle_actions(
                entries=[self._promote_entry(self.student1, action="withdrawn", target_year="")],
                created_by=self.admin_staff_member,
            )
        self._give_role_only(self.admin_user, ["manage_student_promotion"])
        client = self._client_as(self.admin_user)
        resp = client.get("/api/students/promotion/history/?action=withdrawn", HTTP_HOST=self.DOMAIN)
        self.assertEqual(len(resp.data), 1)
