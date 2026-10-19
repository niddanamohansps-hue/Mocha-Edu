import datetime
from decimal import Decimal

from django.core import mail
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connection
from django.test import TestCase, TransactionTestCase
from django.utils import timezone
from django_tenants.utils import tenant_context
from rest_framework.test import APIClient

from accounts.models import User
from accounts.utils.crypto import encrypt_secret, decrypt_secret
from organizations.models import Organization, Domain
from roles.models import Permission, Role, UserRole
from .models import AuditLog
from .audit import log_action


class CryptoUtilTest(TestCase):
    def test_round_trip(self):
        token = encrypt_secret("Sup3rSecret!")
        self.assertNotEqual(token, "Sup3rSecret!")
        self.assertEqual(decrypt_secret(token), "Sup3rSecret!")

    def test_legacy_plaintext_falls_back_gracefully(self):
        # Simulates a row written before encryption was introduced (e.g. seeded
        # test data) - must not raise, must return the value unchanged.
        self.assertEqual(decrypt_secret("plain-old-password"), "plain-old-password")

    def test_none_and_empty_are_safe(self):
        self.assertIsNone(encrypt_secret(None))
        self.assertEqual(decrypt_secret(""), "")


class AuditLogTenantIsolationTest(TransactionTestCase):
    def setUp(self):
        connection.set_schema_to_public()
        self.school_a = Organization.objects.create(
            schema_name="audit_school_a", name="Audit School A"
        )
        Domain.objects.create(
            domain="auditA.localhost", tenant=self.school_a, is_primary=True
        )
        self.school_b = Organization.objects.create(
            schema_name="audit_school_b", name="Audit School B"
        )
        Domain.objects.create(
            domain="auditB.localhost", tenant=self.school_b, is_primary=True
        )

    def tearDown(self):
        connection.set_schema_to_public()
        self.school_a.delete(force_drop=True)
        self.school_b.delete(force_drop=True)

    def test_audit_logs_are_isolated_per_tenant(self):
        with tenant_context(self.school_a):
            AuditLog.objects.create(
                actor_username="admin_a", action="role_created", model_name="Role"
            )

        with tenant_context(self.school_b):
            count_in_b = AuditLog.objects.count()
            self.assertEqual(
                count_in_b,
                0,
                "TENANT ISOLATION FAILURE: School B can see School A's audit log entries",
            )

        with tenant_context(self.school_a):
            count_in_a = AuditLog.objects.count()
            self.assertEqual(count_in_a, 1)

    def test_log_action_never_raises_on_failure(self):
        class FakeRequest:
            user = None
            META = {}

        # Passing an object with no real request attributes must not raise -
        # audit logging is best-effort and must never break the caller.
        try:
            log_action(FakeRequest(), action="test_action", model_name="Whatever")
        except Exception as exc:  # pragma: no cover - explicit failure signal
            self.fail(f"log_action raised unexpectedly: {exc}")


class AuditLogAPITests(TransactionTestCase):
    """
    Focused tests for GET /api/audit-logs/ and GET /api/audit-logs/{id}/.
    Mirrors the _build_school/_build_user/_client_as pattern already used
    by fees/attendance/timetable/examinations/parent_portal tests.py.
    """

    SCHEMA_NAME = "auditapi_test_school"
    DOMAIN = "auditapitest.localhost"

    OTHER_SCHEMA_NAME = "auditapi_other_school"
    OTHER_DOMAIN = "auditapiother.localhost"

    def setUp(self):
        connection.set_schema_to_public()
        self.school = Organization.objects.create(
            schema_name=self.SCHEMA_NAME, name="Audit API Test School"
        )
        Domain.objects.create(domain=self.DOMAIN, tenant=self.school, is_primary=True)

        self.other_school = Organization.objects.create(
            schema_name=self.OTHER_SCHEMA_NAME, name="Audit API Other School"
        )
        Domain.objects.create(
            domain=self.OTHER_DOMAIN, tenant=self.other_school, is_primary=True
        )

    def tearDown(self):
        connection.set_schema_to_public()
        self.school.delete(force_drop=True)
        self.other_school.delete(force_drop=True)

    def _build_user(self, school, username, permission_codenames):
        user = User.objects.create_user(
            username=username, email=f"{username}@auditapitest.com", password="Pass1234!"
        )
        with tenant_context(school):
            role = Role.objects.create(
                name=f"role-{username}", slug=f"role-{username}", is_system_role=False
            )
            if permission_codenames:
                role.permissions.set(
                    Permission.objects.filter(codename__in=permission_codenames)
                )
            UserRole.objects.create(user=user, role=role)
        return user

    def _client_as(self, user, domain, password="Pass1234!"):
        client = APIClient()
        resp = client.post(
            "/api/auth/login/",
            {"username": user.username, "password": password},
            HTTP_HOST=domain,
        )
        assert resp.status_code == 200, resp.data
        return client

    def _create_audit_log(self, school, **kwargs):
        with tenant_context(school):
            defaults = dict(
                action="test_action",
                model_name="TestModel",
                object_id="OBJ-1",
                actor_username="someone",
            )
            defaults.update(kwargs)
            return AuditLog.objects.create(**defaults)

    # 1. Authenticated + permitted -> can list
    def test_authenticated_user_with_permission_can_list(self):
        self._create_audit_log(self.school, action="role_created")
        user = self._build_user(self.school, "audituser1", ["view_audit_log"])
        client = self._client_as(user, self.DOMAIN)
        resp = client.get("/api/audit-logs/", HTTP_HOST=self.DOMAIN)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["count"], 1)

    # 2. Unauthenticated -> 401
    def test_unauthenticated_user_gets_401(self):
        client = APIClient()
        resp = client.get("/api/audit-logs/", HTTP_HOST=self.DOMAIN)
        self.assertEqual(resp.status_code, 401)

    # 3. Authenticated, no permission -> 403
    def test_authenticated_user_without_permission_gets_403(self):
        user = self._build_user(self.school, "audituser2", [])
        client = self._client_as(user, self.DOMAIN)
        resp = client.get("/api/audit-logs/", HTTP_HOST=self.DOMAIN)
        self.assertEqual(resp.status_code, 403)

    # 4. Tenant isolation - list
    def test_tenant_a_cannot_see_tenant_b_audit_logs(self):
        self._create_audit_log(self.school, action="a_action")
        self._create_audit_log(self.other_school, action="b_action")
        user = self._build_user(self.school, "audituser3", ["view_audit_log"])
        client = self._client_as(user, self.DOMAIN)
        resp = client.get("/api/audit-logs/", HTTP_HOST=self.DOMAIN)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["count"], 1)
        self.assertEqual(resp.data["results"][0]["action"], "a_action")

    # 5. Tenant isolation - retrieve by id
    def test_tenant_a_cannot_retrieve_tenant_b_audit_log_by_id(self):
        log_b = self._create_audit_log(self.other_school, action="b_action")
        user = self._build_user(self.school, "audituser4", ["view_audit_log"])
        client = self._client_as(user, self.DOMAIN)
        resp = client.get(f"/api/audit-logs/{log_b.id}/", HTTP_HOST=self.DOMAIN)
        self.assertEqual(
            resp.status_code,
            404,
            "TENANT ISOLATION FAILURE: Tenant A retrieved Tenant B's audit log by ID",
        )

    # 6/7. POST rejected (read-only)
    def test_post_is_rejected(self):
        user = self._build_user(self.school, "audituser5", ["view_audit_log"])
        client = self._client_as(user, self.DOMAIN)
        resp = client.post(
            "/api/audit-logs/",
            {"action": "x", "model_name": "y"},
            HTTP_HOST=self.DOMAIN,
        )
        self.assertEqual(resp.status_code, 405)

    # 8. PUT/PATCH rejected
    def test_put_is_rejected(self):
        log = self._create_audit_log(self.school)
        user = self._build_user(self.school, "audituser6", ["view_audit_log"])
        client = self._client_as(user, self.DOMAIN)
        resp = client.put(
            f"/api/audit-logs/{log.id}/", {"action": "x"}, HTTP_HOST=self.DOMAIN
        )
        self.assertEqual(resp.status_code, 405)

    def test_patch_is_rejected(self):
        log = self._create_audit_log(self.school)
        user = self._build_user(self.school, "audituser7", ["view_audit_log"])
        client = self._client_as(user, self.DOMAIN)
        resp = client.patch(
            f"/api/audit-logs/{log.id}/", {"action": "x"}, HTTP_HOST=self.DOMAIN
        )
        self.assertEqual(resp.status_code, 405)

    # 9. DELETE rejected
    def test_delete_is_rejected(self):
        log = self._create_audit_log(self.school)
        user = self._build_user(self.school, "audituser8", ["view_audit_log"])
        client = self._client_as(user, self.DOMAIN)
        resp = client.delete(f"/api/audit-logs/{log.id}/", HTTP_HOST=self.DOMAIN)
        self.assertEqual(resp.status_code, 405)

    # 10. Pagination
    def test_pagination_response_shape_and_page_size(self):
        for i in range(3):
            self._create_audit_log(self.school, action=f"action_{i}")
        user = self._build_user(self.school, "audituser9", ["view_audit_log"])
        client = self._client_as(user, self.DOMAIN)
        resp = client.get("/api/audit-logs/?page_size=2", HTTP_HOST=self.DOMAIN)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(
            set(resp.data.keys()), {"count", "next", "previous", "results"}
        )
        self.assertEqual(resp.data["count"], 3)
        self.assertEqual(len(resp.data["results"]), 2)
        self.assertIsNotNone(resp.data["next"])

    # 11. Default ordering newest-first
    def test_default_ordering_is_newest_first(self):
        self._create_audit_log(self.school, action="first")
        self._create_audit_log(self.school, action="second")
        user = self._build_user(self.school, "audituser10", ["view_audit_log"])
        client = self._client_as(user, self.DOMAIN)
        resp = client.get("/api/audit-logs/", HTTP_HOST=self.DOMAIN)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["results"][0]["action"], "second")
        self.assertEqual(resp.data["results"][1]["action"], "first")

    # 12. action filter
    def test_action_filter(self):
        self._create_audit_log(self.school, action="role_created")
        self._create_audit_log(self.school, action="role_deleted")
        user = self._build_user(self.school, "audituser11", ["view_audit_log"])
        client = self._client_as(user, self.DOMAIN)
        resp = client.get("/api/audit-logs/?action=role_created", HTTP_HOST=self.DOMAIN)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["count"], 1)
        self.assertEqual(resp.data["results"][0]["action"], "role_created")

    # 13. model_name filter
    def test_model_name_filter(self):
        self._create_audit_log(self.school, model_name="Student")
        self._create_audit_log(self.school, model_name="Role")
        user = self._build_user(self.school, "audituser12", ["view_audit_log"])
        client = self._client_as(user, self.DOMAIN)
        resp = client.get("/api/audit-logs/?model_name=Student", HTTP_HOST=self.DOMAIN)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["count"], 1)
        self.assertEqual(resp.data["results"][0]["model_name"], "Student")

    # 14. object_id filter
    def test_object_id_filter(self):
        self._create_audit_log(self.school, object_id="STU-2026-00125")
        self._create_audit_log(self.school, object_id="STU-2026-00126")
        user = self._build_user(self.school, "audituser13", ["view_audit_log"])
        client = self._client_as(user, self.DOMAIN)
        resp = client.get(
            "/api/audit-logs/?object_id=STU-2026-00125", HTTP_HOST=self.DOMAIN
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["count"], 1)

    # 15. date_from / date_to filters
    def test_date_from_and_date_to_filters(self):
        with tenant_context(self.school):
            old_log = AuditLog.objects.create(action="old", model_name="X")
            AuditLog.objects.filter(id=old_log.id).update(
                created_at=timezone.now() - datetime.timedelta(days=10)
            )
            AuditLog.objects.create(action="recent", model_name="X")

        user = self._build_user(self.school, "audituser14", ["view_audit_log"])
        client = self._client_as(user, self.DOMAIN)

        today = timezone.now().date().isoformat()
        resp = client.get(f"/api/audit-logs/?date_from={today}", HTTP_HOST=self.DOMAIN)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["count"], 1)
        self.assertEqual(resp.data["results"][0]["action"], "recent")

        five_days_ago = (timezone.now() - datetime.timedelta(days=5)).date().isoformat()
        resp2 = client.get(f"/api/audit-logs/?date_to={five_days_ago}", HTTP_HOST=self.DOMAIN)
        self.assertEqual(resp2.status_code, 200)
        self.assertEqual(resp2.data["count"], 1)
        self.assertEqual(resp2.data["results"][0]["action"], "old")

    # 16. Invalid date filter must not 500
    def test_invalid_date_filter_does_not_500(self):
        self._create_audit_log(self.school)
        user = self._build_user(self.school, "audituser15", ["view_audit_log"])
        client = self._client_as(user, self.DOMAIN)
        resp = client.get("/api/audit-logs/?date_from=not-a-date", HTTP_HOST=self.DOMAIN)
        self.assertNotEqual(resp.status_code, 500)
        self.assertEqual(resp.status_code, 400)

    # 17. Serializer does not leak unexpected/sensitive fields
    def test_serializer_fields_do_not_include_unexpected_sensitive_keys(self):
        self._create_audit_log(self.school, changes={"name": "Role X"})
        user = self._build_user(self.school, "audituser16", ["view_audit_log"])
        client = self._client_as(user, self.DOMAIN)
        resp = client.get("/api/audit-logs/", HTTP_HOST=self.DOMAIN)
        self.assertEqual(resp.status_code, 200)
        result = resp.data["results"][0]
        expected_fields = {
            "id", "actor_id", "actor_username", "action", "model_name",
            "object_id", "changes", "ip_address", "user_agent", "created_at",
        }
        self.assertEqual(set(result.keys()), expected_fields)
        for forbidden in ("password", "token", "secret", "credential"):
            self.assertNotIn(forbidden, result)

    # 18. actor_username filter
    def test_actor_username_filter(self):
        self._create_audit_log(self.school, actor_username="alice_admin", action="action_1")
        self._create_audit_log(self.school, actor_username="bob_teacher", action="action_2")
        user = self._build_user(self.school, "audituser17", ["view_audit_log"])
        client = self._client_as(user, self.DOMAIN)
        resp = client.get("/api/audit-logs/?actor_username=alice", HTTP_HOST=self.DOMAIN)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["count"], 1)
        self.assertEqual(resp.data["results"][0]["actor_username"], "alice_admin")

    # 19. search filter across username, action, model_name, object_id
    def test_search_filter(self):
        self._create_audit_log(self.school, actor_username="john", action="role_created", model_name="Role", object_id="ROL-1")
        self._create_audit_log(self.school, actor_username="mary", action="student_enrolled", model_name="Student", object_id="STU-99")
        user = self._build_user(self.school, "audituser18", ["view_audit_log"])
        client = self._client_as(user, self.DOMAIN)

        # Search by keyword matching object_id
        resp = client.get("/api/audit-logs/?search=STU-99", HTTP_HOST=self.DOMAIN)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["count"], 1)
        self.assertEqual(resp.data["results"][0]["object_id"], "STU-99")

        # Search by keyword matching action
        resp2 = client.get("/api/audit-logs/?search=role_created", HTTP_HOST=self.DOMAIN)
        self.assertEqual(resp2.status_code, 200)
        self.assertEqual(resp2.data["count"], 1)
        self.assertEqual(resp2.data["results"][0]["action"], "role_created")

    # 20. ordering filter
    def test_ordering_filter(self):
        self._create_audit_log(self.school, action="alpha")
        self._create_audit_log(self.school, action="beta")
        user = self._build_user(self.school, "audituser19", ["view_audit_log"])
        client = self._client_as(user, self.DOMAIN)

        resp = client.get("/api/audit-logs/?ordering=created_at", HTTP_HOST=self.DOMAIN)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["results"][0]["action"], "alpha")
        self.assertEqual(resp.data["results"][1]["action"], "beta")

    # 21. date_from > date_to validation
    def test_date_from_greater_than_date_to_returns_400(self):
        self._create_audit_log(self.school)
        user = self._build_user(self.school, "audituser20", ["view_audit_log"])
        client = self._client_as(user, self.DOMAIN)
        resp = client.get("/api/audit-logs/?date_from=2026-10-15&date_to=2026-10-10", HTTP_HOST=self.DOMAIN)
        self.assertEqual(resp.status_code, 400)
        self.assertIn("date_from", resp.data)

    # 22. metadata endpoint returns distinct actions and models
    def test_metadata_endpoint_returns_distinct_actions_and_models(self):
        self._create_audit_log(self.school, action="action_a", model_name="ModelA")
        self._create_audit_log(self.school, action="action_a", model_name="ModelB")
        self._create_audit_log(self.school, action="action_b", model_name="ModelA")

        user = self._build_user(self.school, "audituser21", ["view_audit_log"])
        client = self._client_as(user, self.DOMAIN)
        resp = client.get("/api/audit-logs/metadata/", HTTP_HOST=self.DOMAIN)
        self.assertEqual(resp.status_code, 200)
        self.assertIn("actions", resp.data)
        self.assertIn("model_names", resp.data)
        self.assertEqual(set(resp.data["actions"]), {"action_a", "action_b"})
        self.assertEqual(set(resp.data["model_names"]), {"ModelA", "ModelB"})

    # 23. metadata endpoint requires permission
    def test_metadata_endpoint_requires_permission(self):
        user = self._build_user(self.school, "audituser22", [])
        client = self._client_as(user, self.DOMAIN)
        resp = client.get("/api/audit-logs/metadata/", HTTP_HOST=self.DOMAIN)
        self.assertEqual(resp.status_code, 403)

    # 24. metadata endpoint tenant isolation
    def test_metadata_endpoint_tenant_isolation(self):
        self._create_audit_log(self.school, action="school_a_action", model_name="SchoolAModel")
        self._create_audit_log(self.other_school, action="school_b_action", model_name="SchoolBModel")

        user = self._build_user(self.school, "audituser23", ["view_audit_log"])
        client = self._client_as(user, self.DOMAIN)
        resp = client.get("/api/audit-logs/metadata/", HTTP_HOST=self.DOMAIN)
        self.assertEqual(resp.status_code, 200)
        self.assertIn("school_a_action", resp.data["actions"])
        self.assertNotIn("school_b_action", resp.data["actions"])
        self.assertIn("SchoolAModel", resp.data["model_names"])
        self.assertNotIn("SchoolBModel", resp.data["model_names"])


class SeedDemoSchoolCommandTest(TransactionTestCase):
    """
    Focused tests for the seed_demo_school management command. Each test
    runs the command at a small scale (students=15) against the real
    tenant-provisioning path (Organization.objects.create() with
    auto_create_schema=True) - exactly what a developer running it for
    real would trigger, just smaller. tearDown always attempts --clear so
    a failure in one test can never leave the fixed demo schema name
    ('greenvalley_demo') behind to collide with the next test.
    """

    SCHEMA_NAME = "greenvalley_demo"

    def tearDown(self):
        try:
            call_command("seed_demo_school", clear=True)
        except Exception:
            pass
        connection.set_schema_to_public()

    def _seed(self, **kwargs):
        kwargs.setdefault("students", 15)
        kwargs.setdefault("seed", 99)
        call_command("seed_demo_school", **kwargs)

    def test_creates_demo_tenant_with_correct_student_count(self):
        self._seed()
        organization = Organization.objects.get(schema_name=self.SCHEMA_NAME)
        self.assertEqual(organization.name, "Green Valley International School")
        with tenant_context(organization):
            from students.models import Student

            self.assertEqual(Student.objects.count(), 15)

    def test_academic_and_staff_relationships_valid(self):
        self._seed()
        organization = Organization.objects.get(schema_name=self.SCHEMA_NAME)
        with tenant_context(organization):
            from academics.models import SubjectAssignment
            from staff.models import Instructor

            self.assertEqual(Instructor.objects.count(), 35)
            assignments = list(SubjectAssignment.objects.select_related("section__level", "subject__level"))
            self.assertTrue(assignments)
            for assignment in assignments:
                # No orphaned academic records: every assignment's subject
                # belongs to the same level as its section, and every
                # assignment has a real instructor.
                self.assertEqual(assignment.section.level_id, assignment.subject.level_id)
                self.assertIsNotNone(assignment.instructor_id)

    def test_student_parent_relationships_valid(self):
        self._seed()
        organization = Organization.objects.get(schema_name=self.SCHEMA_NAME)
        with tenant_context(organization):
            from families.models import StudentParentRelation

            relations = list(StudentParentRelation.objects.all())
            self.assertTrue(relations)
            for relation in relations:
                self.assertIsNotNone(relation.student_id)
                self.assertIsNotNone(relation.parent_id)

    def test_examination_relationships_valid(self):
        self._seed()
        organization = Organization.objects.get(schema_name=self.SCHEMA_NAME)
        with tenant_context(organization):
            from examinations.models import Examination, ExamResult

            examinations = list(Examination.objects.all())
            self.assertEqual(len(examinations), 5)
            self.assertEqual(sum(1 for e in examinations if e.is_published), 4)
            self.assertEqual(sum(1 for e in examinations if not e.is_published), 1)
            self.assertTrue(ExamResult.objects.exists())
            for result in ExamResult.objects.all():
                self.assertIsNotNone(result.student_id)
                self.assertIsNotNone(result.examination_id)

    def test_fee_relationships_valid(self):
        self._seed()
        organization = Organization.objects.get(schema_name=self.SCHEMA_NAME)
        with tenant_context(organization):
            from fees.models import Payment, StudentFee

            self.assertTrue(StudentFee.objects.exists())
            self.assertTrue(Payment.objects.exists())
            for payment in Payment.objects.all():
                self.assertGreater(payment.amount, 0)
                self.assertIsNotNone(payment.student_id)

    def test_tenant_data_created_in_correct_schema(self):
        self._seed()
        connection.set_schema_to_public()
        self.assertNotIn("students_student", connection.introspection.table_names())
        organization = Organization.objects.get(schema_name=self.SCHEMA_NAME)
        with tenant_context(organization):
            from students.models import Student

            self.assertTrue(Student.objects.exists())

    def test_rerun_without_clear_refuses_and_creates_no_duplicate(self):
        self._seed()
        with self.assertRaises(CommandError):
            self._seed()
        self.assertEqual(Organization.objects.filter(schema_name=self.SCHEMA_NAME).count(), 1)

    def test_clear_does_not_affect_other_tenant_data(self):
        other = Organization.objects.create(schema_name="unrelated_demo_test_school", name="Unrelated School")
        Domain.objects.create(domain="unrelated-demo-test.localhost", tenant=other, is_primary=True)
        try:
            with tenant_context(other):
                from profiles.models import Profile
                from students.models import Student

                profile = Profile.objects.create(first_name="Keep", last_name="Me")
                Student.objects.create(profile=profile, enrollment_id="KEEP-0001", status="active")

            self._seed()
            call_command("seed_demo_school", clear=True)

            self.assertFalse(Organization.objects.filter(schema_name=self.SCHEMA_NAME).exists())
            self.assertTrue(Organization.objects.filter(schema_name="unrelated_demo_test_school").exists())
            with tenant_context(other):
                from students.models import Student

                self.assertEqual(Student.objects.count(), 1)
        finally:
            connection.set_schema_to_public()
            other.delete(force_drop=True)

    def test_deterministic_seed_is_reproducible(self):
        def student_fingerprint():
            organization = Organization.objects.get(schema_name=self.SCHEMA_NAME)
            with tenant_context(organization):
                from students.models import Student

                return sorted(
                    (s.enrollment_id, s.profile.first_name, s.profile.last_name, s.status)
                    for s in Student.objects.select_related("profile")
                )

        self._seed(seed=42)
        first_run = student_fingerprint()
        call_command("seed_demo_school", clear=True)

        self._seed(seed=42)
        second_run = student_fingerprint()

        self.assertEqual(first_run, second_run)

    def test_no_real_email_sent_and_no_secrets_in_audit_logs(self):
        mail.outbox = []
        self._seed()
        self.assertEqual(len(mail.outbox), 0, "seed_demo_school must never send a real email")

        organization = Organization.objects.get(schema_name=self.SCHEMA_NAME)
        with tenant_context(organization):
            from core.models import AuditLog as TenantAuditLog
            from notifications.models import EmailOutboxEvent

            # Outbox rows were created directly (never via queue_email()),
            # so no Celery dispatch was ever attempted either.
            self.assertTrue(EmailOutboxEvent.objects.exists())

            for log in TenantAuditLog.objects.all():
                blob = f"{log.changes} {log.user_agent or ''}".lower()
                for forbidden in ("demopass", "password", "token", "secret"):
                    self.assertNotIn(forbidden, blob)


class SeedRealisticSchoolCommandTest(TransactionTestCase):
    """
    Focused tests for the seed_realistic_school management command - a
    separate tenant/schema from seed_demo_school's own test class above,
    so the two can never collide. Mirrors SeedDemoSchoolCommandTest's
    pattern exactly (small scale, --clear in tearDown so a failure can
    never leave 'sunrisevalley_school' behind to collide with the next
    test), covering the 10 points this seeder was explicitly required to
    test: realistic data, repeatability, no duplicates, relationship
    validity, tenant isolation, fee-total consistency, payment-allocation
    consistency, examination relationship validity, attendance
    relationship validity, and promotion relationship validity.
    """

    SCHEMA_NAME = "sunrisevalley_school"

    def tearDown(self):
        try:
            call_command("seed_realistic_school", clear=True)
        except Exception:
            pass
        connection.set_schema_to_public()

    def _seed(self, **kwargs):
        kwargs.setdefault("students", 25)
        kwargs.setdefault("seed", 99)
        kwargs.setdefault("attendance_days", 10)
        call_command("seed_realistic_school", **kwargs)

    # --- 1. Realistic data ---------------------------------------------

    def test_generates_realistic_non_placeholder_names(self):
        self._seed()
        organization = Organization.objects.get(schema_name=self.SCHEMA_NAME)
        with tenant_context(organization):
            from students.models import Student

            names = [(s.profile.first_name, s.profile.last_name) for s in Student.objects.select_related("profile")]
            self.assertTrue(names)
            placeholder_markers = ("test", "demo", "student0", "john", "doe")
            for first, last in names:
                blob = f"{first} {last}".lower()
                for marker in placeholder_markers:
                    self.assertNotIn(marker, blob, f"Placeholder-looking name found: {first} {last}")
            # Real regional variety, not the same handful of names repeated.
            self.assertGreater(len(set(names)), max(1, len(names) // 2))

    # --- 2. Repeatable / deterministic ----------------------------------

    def test_deterministic_seed_is_reproducible(self):
        def student_fingerprint():
            organization = Organization.objects.get(schema_name=self.SCHEMA_NAME)
            with tenant_context(organization):
                from students.models import Student

                return sorted(
                    (s.enrollment_id, s.profile.first_name, s.profile.last_name, s.status)
                    for s in Student.objects.select_related("profile")
                )

        self._seed(seed=42)
        first_run = student_fingerprint()
        call_command("seed_realistic_school", clear=True)

        self._seed(seed=42)
        second_run = student_fingerprint()

        self.assertEqual(first_run, second_run)

    # --- 3. No duplicate records ----------------------------------------

    def test_no_duplicate_enrollment_or_employee_ids(self):
        self._seed()
        organization = Organization.objects.get(schema_name=self.SCHEMA_NAME)
        with tenant_context(organization):
            from django.db.models import Count

            from staff.models import StaffMember
            from students.models import Student

            dup_enrollments = Student.objects.values("enrollment_id").annotate(n=Count("id")).filter(n__gt=1)
            self.assertFalse(list(dup_enrollments))
            dup_employees = StaffMember.objects.values("employee_id").annotate(n=Count("id")).filter(n__gt=1)
            self.assertFalse(list(dup_employees))

    def test_rerun_without_clear_refuses_and_creates_no_duplicate(self):
        self._seed()
        with self.assertRaises(CommandError):
            self._seed()
        self.assertEqual(Organization.objects.filter(schema_name=self.SCHEMA_NAME).count(), 1)

    # --- 4. Relationship validity ---------------------------------------

    def test_family_and_subject_assignment_relationships_valid(self):
        self._seed()
        organization = Organization.objects.get(schema_name=self.SCHEMA_NAME)
        with tenant_context(organization):
            from academics.models import SubjectAssignment
            from families.models import StudentParentRelation

            relations = list(StudentParentRelation.objects.all())
            self.assertTrue(relations)
            for relation in relations:
                self.assertIsNotNone(relation.student_id)
                self.assertIsNotNone(relation.parent_id)

            assignments = list(SubjectAssignment.objects.select_related("section__level", "subject__level"))
            self.assertTrue(assignments)
            for assignment in assignments:
                self.assertEqual(assignment.section.level_id, assignment.subject.level_id)
                self.assertIsNotNone(assignment.instructor_id)

    # --- 5. Tenant isolation ---------------------------------------------

    def test_clear_does_not_affect_other_tenant_data(self):
        other = Organization.objects.create(schema_name="unrelated_realistic_test_school", name="Unrelated School")
        Domain.objects.create(domain="unrelated-realistic-test.localhost", tenant=other, is_primary=True)
        try:
            with tenant_context(other):
                from profiles.models import Profile
                from students.models import Student

                profile = Profile.objects.create(first_name="Keep", last_name="Me")
                Student.objects.create(profile=profile, enrollment_id="KEEP-0001", status="active")

            self._seed()
            call_command("seed_realistic_school", clear=True)

            self.assertFalse(Organization.objects.filter(schema_name=self.SCHEMA_NAME).exists())
            self.assertTrue(Organization.objects.filter(schema_name="unrelated_realistic_test_school").exists())
            with tenant_context(other):
                from students.models import Student

                self.assertEqual(Student.objects.count(), 1)
        finally:
            connection.set_schema_to_public()
            other.delete(force_drop=True)

    # --- 6/7. Fee totals and payment allocations consistent -------------

    def test_fee_totals_and_payment_allocations_consistent(self):
        self._seed()
        organization = Organization.objects.get(schema_name=self.SCHEMA_NAME)
        with tenant_context(organization):
            from fees.models import Payment, PaymentAllocation, StudentFee

            self.assertTrue(StudentFee.objects.exists())
            self.assertTrue(Payment.objects.exists())

            for student_fee in StudentFee.objects.all():
                allocated = sum(
                    (a.amount for a in PaymentAllocation.objects.filter(student_fee=student_fee)), Decimal("0")
                )
                net_due = student_fee.amount_due - student_fee.discount_amount
                self.assertLessEqual(allocated, net_due, f"StudentFee {student_fee.id} over-allocated")

            for payment in Payment.objects.all():
                self.assertGreater(payment.amount, 0)
                allocation_sum = sum(
                    (a.amount for a in PaymentAllocation.objects.filter(payment=payment)), Decimal("0")
                )
                self.assertEqual(allocation_sum, payment.amount)

    # --- 8. Examination relationships valid ------------------------------

    def test_examination_relationships_valid(self):
        self._seed()
        organization = Organization.objects.get(schema_name=self.SCHEMA_NAME)
        with tenant_context(organization):
            from examinations.models import ExamMark, ExamResult, Examination

            examinations = list(Examination.objects.all())
            self.assertEqual(len(examinations), 4)
            self.assertTrue(any(e.is_published for e in examinations))
            self.assertTrue(any(not e.is_published for e in examinations))

            self.assertTrue(ExamMark.objects.exists())
            for mark in ExamMark.objects.select_related("exam_schedule", "student")[:50]:
                self.assertIsNotNone(mark.exam_schedule_id)
                self.assertIsNotNone(mark.student_id)

            self.assertTrue(ExamResult.objects.exists())
            for result in ExamResult.objects.select_related("student", "examination")[:50]:
                self.assertIsNotNone(result.student_id)
                self.assertIsNotNone(result.examination_id)

    # --- 9. Attendance relationships valid -------------------------------

    def test_attendance_relationships_valid(self):
        self._seed()
        organization = Organization.objects.get(schema_name=self.SCHEMA_NAME)
        with tenant_context(organization):
            from django.db.models import Count

            from attendance.models import AttendanceSession, StudentAttendance

            self.assertTrue(AttendanceSession.objects.exists())
            self.assertTrue(StudentAttendance.objects.exists())

            dup_sessions = (
                AttendanceSession.objects.values("section", "date").annotate(n=Count("id")).filter(n__gt=1)
            )
            self.assertFalse(list(dup_sessions))

            for record in StudentAttendance.objects.select_related("session", "student")[:50]:
                self.assertIsNotNone(record.session_id)
                self.assertIsNotNone(record.student_id)

    # --- 10. Promotion relationships valid -------------------------------

    def test_promotion_relationships_valid(self):
        self._seed(academic_years=2)
        organization = Organization.objects.get(schema_name=self.SCHEMA_NAME)
        with tenant_context(organization):
            from students.models import PromotionRecord

            records = list(PromotionRecord.objects.select_related(
                "student", "source_level", "target_level", "source_student_level", "target_student_level"
            ))
            self.assertTrue(records)
            for record in records:
                self.assertIn(record.action, ("promoted", "retained"))
                self.assertIsNotNone(record.student_id)
                self.assertIsNotNone(record.source_level_id)
                self.assertIsNotNone(record.target_level_id)
                self.assertNotEqual(record.source_student_level_id, record.target_student_level_id)

    # --- No real email ----------------------------------------------------

    def test_no_real_email_sent(self):
        mail.outbox = []
        self._seed()
        self.assertEqual(len(mail.outbox), 0, "seed_realistic_school must never send a real email")
