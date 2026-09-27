import uuid as uuid_module

from django.db import connection
from django.test import TransactionTestCase
from django_tenants.utils import tenant_context
from rest_framework.test import APIClient

from accounts.models import User
from families.models import Parent, StudentParentRelation
from organizations.models import Domain, Organization
from profiles.models import Profile
from roles.models import Role, UserRole
from staff.models import Instructor, StaffMember
from students.models import Student

from .models import Notification
from .services import notify, notify_many


class NotificationFixtureMixin:
    """Mirrors students/fees/parent_portal tests.py exactly."""

    SCHEMA_NAME = "notif_test_school"
    DOMAIN = "notiftest.localhost"

    def _build_school(self, schema_name=None, domain=None, name="Notifications Test School"):
        schema_name = schema_name or self.SCHEMA_NAME
        domain = domain or self.DOMAIN
        connection.set_schema_to_public()
        school = Organization.objects.create(schema_name=schema_name, name=name)
        Domain.objects.create(domain=domain, tenant=school, is_primary=True)
        return school

    def _build_user_with_profile(self, username, role_slug, first_name="Test", last_name="User"):
        """
        Builds a User directly (never via a shared "_build_user + UserRole"
        helper followed by a manual Profile.create()) so the Profile is
        linked BEFORE the UserRole is created. profiles.signals.
        create_profile_for_role fires on UserRole post_save and
        auto-creates a Profile for any role NOT in its
        ["student", "instructor"] skip list - creating the UserRole before
        a real Profile exists (or creating a second Profile afterward)
        produces a duplicate Profile.MultipleObjectsReturned, exactly the
        mistake already found and fixed twice this session (fees/tests.py,
        students/tests.py).
        """
        user = User.objects.create_user(
            username=username, email=f"{username}@notiftest.com", password="Pass1234!"
        )
        with tenant_context(self.school):
            Profile.objects.create(user_id=user.id, first_name=first_name, last_name=last_name)
            role, _ = Role.objects.get_or_create(
                slug=role_slug, defaults={"name": role_slug.title(), "is_system_role": True}
            )
            UserRole.objects.create(user=user, role=role)
        return user

    def _client_as(self, user, password="Pass1234!"):
        client = APIClient()
        resp = client.post(
            "/api/auth/login/", {"username": user.username, "password": password}, HTTP_HOST=self.DOMAIN
        )
        assert resp.status_code == 200, resp.data
        return client

    def setUp(self):
        self.school = self._build_school()

        self.owner_user = self._build_user_with_profile("notif_owner", "owner", "Own", "Er")
        self.staff_user = self._build_user_with_profile("notif_staff", "staff", "Sta", "Ff")

        # Instructor - "instructor" IS in profiles.signals' skip list, so a
        # student_record/staff_record-style manual Profile is safe here too,
        # but we use the same safe helper for consistency.
        self.instructor_user = self._build_user_with_profile("notif_instructor", "instructor", "Ins", "Tructor")
        with tenant_context(self.school):
            instr_profile = Profile.objects.filter(user_id=self.instructor_user.id).first()
            instr_staff = StaffMember.objects.create(
                profile=instr_profile, employee_id="EMP-NOTIF-1", designation="Teacher"
            )
            self.instructor = Instructor.objects.create(staff_member=instr_staff, specialization="Math")

        self.student_user = self._build_user_with_profile("notif_student", "student", "Stu", "Dent")
        with tenant_context(self.school):
            student_profile = Profile.objects.filter(user_id=self.student_user.id).first()
            self.student = Student.objects.create(
                profile=student_profile, enrollment_id="ENR-NOTIF-1", status="active"
            )

        self.parent_user = self._build_user_with_profile("notif_parent", "parent", "Par", "Ent")
        with tenant_context(self.school):
            parent_profile = Profile.objects.filter(user_id=self.parent_user.id).first()
            self.parent = Parent.objects.create(profile=parent_profile, occupation="Engineer")
            StudentParentRelation.objects.create(
                student=self.student, parent=self.parent, relation_type="mother", is_primary_contact=True
            )

        # A second user with no notifications, used as "User B" for IDOR tests.
        self.other_user = self._build_user_with_profile("notif_other", "staff", "Oth", "Er")

        # A second, separate tenant to prove cross-tenant isolation.
        self.school2 = self._build_school(
            schema_name="notif_test_school2", domain="notiftest2.localhost", name="Notifications Test School 2"
        )

    def tearDown(self):
        connection.set_schema_to_public()
        self.school.delete(force_drop=True)
        self.school2.delete(force_drop=True)


class NotificationModelTests(NotificationFixtureMixin, TransactionTestCase):
    def test_notification_created(self):
        with tenant_context(self.school):
            n = Notification.objects.create(recipient_user_id=self.staff_user.id, title="Hello")
            self.assertIsNotNone(n.id)

    def test_uuid_primary_key(self):
        with tenant_context(self.school):
            n = Notification.objects.create(recipient_user_id=self.staff_user.id, title="Hello")
            self.assertIsInstance(n.id, uuid_module.UUID)

    def test_unread_by_default(self):
        with tenant_context(self.school):
            n = Notification.objects.create(recipient_user_id=self.staff_user.id, title="Hello")
            self.assertFalse(n.is_read)

    def test_read_at_nullable(self):
        with tenant_context(self.school):
            n = Notification.objects.create(recipient_user_id=self.staff_user.id, title="Hello")
            self.assertIsNone(n.read_at)

    def test_index_exists(self):
        with tenant_context(self.school):
            index_names = {idx.name for idx in Notification._meta.indexes}
            self.assertIn("notif_recipient_unread_idx", index_names)

    def test_duplicates_allowed(self):
        with tenant_context(self.school):
            Notification.objects.create(recipient_user_id=self.staff_user.id, title="Same")
            Notification.objects.create(recipient_user_id=self.staff_user.id, title="Same")
            self.assertEqual(
                Notification.objects.filter(recipient_user_id=self.staff_user.id, title="Same").count(), 2
            )

    def test_no_table_in_public_schema(self):
        connection.set_schema_to_public()
        self.assertNotIn("notifications_notification", connection.introspection.table_names())


class NotificationServiceTests(NotificationFixtureMixin, TransactionTestCase):
    def test_notify_creates_one_notification(self):
        with tenant_context(self.school):
            n = notify(recipient_user_id=self.staff_user.id, title="Fee due", body="Rs 500 due", category="fee", link="/dashboard/fees")
            self.assertEqual(n.title, "Fee due")
            self.assertEqual(n.category, "fee")
            self.assertEqual(n.link, "/dashboard/fees")

    def test_notify_requires_title(self):
        with tenant_context(self.school):
            with self.assertRaises(ValueError):
                notify(recipient_user_id=self.staff_user.id, title="")

    def test_notify_requires_recipient(self):
        with tenant_context(self.school):
            with self.assertRaises(ValueError):
                notify(recipient_user_id=None, title="Hello")

    def test_notify_optional_body_category_link(self):
        with tenant_context(self.school):
            n = notify(recipient_user_id=self.staff_user.id, title="System notice")
            self.assertEqual(n.body, "")
            self.assertEqual(n.category, "")
            self.assertEqual(n.link, "")

    def test_notify_many_creates_one_per_recipient(self):
        with tenant_context(self.school):
            created = notify_many(
                recipient_user_ids=[self.staff_user.id, self.student_user.id, self.parent_user.id],
                title="Broadcast",
            )
            self.assertEqual(len(created), 3)
            self.assertEqual(Notification.objects.filter(title="Broadcast").count(), 3)

    def test_notify_many_uses_bulk_create_no_duplicate_restriction(self):
        with tenant_context(self.school):
            created = notify_many(
                recipient_user_ids=[self.staff_user.id, self.staff_user.id], title="Twice"
            )
            self.assertEqual(len(created), 2)
            self.assertEqual(Notification.objects.filter(recipient_user_id=self.staff_user.id, title="Twice").count(), 2)

    def test_notify_many_requires_recipients(self):
        with tenant_context(self.school):
            with self.assertRaises(ValueError):
                notify_many(recipient_user_ids=[], title="Hello")

    def test_notify_many_returns_saved_instances_with_pks(self):
        with tenant_context(self.school):
            created = notify_many(recipient_user_ids=[self.staff_user.id], title="Has PK")
            self.assertIsNotNone(created[0].id)


class NotificationAPITests(NotificationFixtureMixin, TransactionTestCase):
    def test_list_own_notifications(self):
        with tenant_context(self.school):
            notify(recipient_user_id=self.staff_user.id, title="Mine")
            notify(recipient_user_id=self.other_user.id, title="Not mine")
        client = self._client_as(self.staff_user)
        resp = client.get("/api/notifications/", HTTP_HOST=self.DOMAIN)
        self.assertEqual(resp.status_code, 200)
        titles = [n["title"] for n in resp.data["results"]]
        self.assertIn("Mine", titles)
        self.assertNotIn("Not mine", titles)

    def test_newest_first(self):
        with tenant_context(self.school):
            notify(recipient_user_id=self.staff_user.id, title="First")
            notify(recipient_user_id=self.staff_user.id, title="Second")
        client = self._client_as(self.staff_user)
        resp = client.get("/api/notifications/", HTTP_HOST=self.DOMAIN)
        self.assertEqual(resp.data["results"][0]["title"], "Second")

    def test_pagination_present(self):
        with tenant_context(self.school):
            for i in range(25):
                notify(recipient_user_id=self.staff_user.id, title=f"N{i}")
        client = self._client_as(self.staff_user)
        resp = client.get("/api/notifications/", HTTP_HOST=self.DOMAIN)
        self.assertEqual(resp.status_code, 200)
        self.assertIn("count", resp.data)
        self.assertIn("next", resp.data)
        self.assertEqual(resp.data["count"], 25)
        self.assertEqual(len(resp.data["results"]), 20)  # page_size

    def test_unread_count(self):
        with tenant_context(self.school):
            notify(recipient_user_id=self.staff_user.id, title="A")
            notify(recipient_user_id=self.staff_user.id, title="B")
        client = self._client_as(self.staff_user)
        resp = client.get("/api/notifications/unread-count/", HTTP_HOST=self.DOMAIN)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["unread_count"], 2)

    def test_mark_one_read(self):
        with tenant_context(self.school):
            n = notify(recipient_user_id=self.staff_user.id, title="A")
        client = self._client_as(self.staff_user)
        resp = client.post(f"/api/notifications/{n.id}/read/", {}, HTTP_HOST=self.DOMAIN)
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.data["is_read"])

    def test_mark_one_read_sets_read_at(self):
        with tenant_context(self.school):
            n = notify(recipient_user_id=self.staff_user.id, title="A")
        client = self._client_as(self.staff_user)
        client.post(f"/api/notifications/{n.id}/read/", {}, HTTP_HOST=self.DOMAIN)
        with tenant_context(self.school):
            n.refresh_from_db()
            self.assertIsNotNone(n.read_at)

    def test_mark_all_read(self):
        with tenant_context(self.school):
            notify(recipient_user_id=self.staff_user.id, title="A")
            notify(recipient_user_id=self.staff_user.id, title="B")
            notify(recipient_user_id=self.staff_user.id, title="C")
        client = self._client_as(self.staff_user)
        resp = client.post("/api/notifications/mark-all-read/", {}, HTTP_HOST=self.DOMAIN)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["updated_count"], 3)
        with tenant_context(self.school):
            self.assertEqual(
                Notification.objects.filter(recipient_user_id=self.staff_user.id, is_read=False).count(), 0
            )

    def test_already_read_mark_read_is_idempotent(self):
        with tenant_context(self.school):
            n = notify(recipient_user_id=self.staff_user.id, title="A")
        client = self._client_as(self.staff_user)
        first = client.post(f"/api/notifications/{n.id}/read/", {}, HTTP_HOST=self.DOMAIN)
        second = client.post(f"/api/notifications/{n.id}/read/", {}, HTTP_HOST=self.DOMAIN)
        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertTrue(second.data["is_read"])

    def test_mark_all_read_when_none_unread(self):
        client = self._client_as(self.staff_user)
        resp = client.post("/api/notifications/mark-all-read/", {}, HTTP_HOST=self.DOMAIN)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["updated_count"], 0)

    def test_nonexistent_notification_returns_404(self):
        client = self._client_as(self.staff_user)
        resp = client.post(f"/api/notifications/{uuid_module.uuid4()}/read/", {}, HTTP_HOST=self.DOMAIN)
        self.assertEqual(resp.status_code, 404)

    def test_client_cannot_create_notification_via_api(self):
        client = self._client_as(self.staff_user)
        # No POST /api/notifications/ (create) endpoint exists at all.
        resp = client.post("/api/notifications/", {"title": "Injected", "recipient_user_id": str(self.other_user.id)}, HTTP_HOST=self.DOMAIN)
        self.assertEqual(resp.status_code, 405)


class NotificationSecurityTests(NotificationFixtureMixin, TransactionTestCase):
    def test_unauthenticated_rejected(self):
        client = APIClient()
        resp = client.get("/api/notifications/", HTTP_HOST=self.DOMAIN)
        self.assertIn(resp.status_code, (401, 403))

    def test_user_a_lists_only_user_a_notifications(self):
        with tenant_context(self.school):
            notify(recipient_user_id=self.staff_user.id, title="A's notification")
            notify(recipient_user_id=self.other_user.id, title="B's notification")
        client = self._client_as(self.staff_user)
        resp = client.get("/api/notifications/", HTTP_HOST=self.DOMAIN)
        titles = [n["title"] for n in resp.data["results"]]
        self.assertEqual(titles, ["A's notification"])

    def test_user_b_lists_only_user_b_notifications(self):
        with tenant_context(self.school):
            notify(recipient_user_id=self.staff_user.id, title="A's notification")
            notify(recipient_user_id=self.other_user.id, title="B's notification")
        client = self._client_as(self.other_user)
        resp = client.get("/api/notifications/", HTTP_HOST=self.DOMAIN)
        titles = [n["title"] for n in resp.data["results"]]
        self.assertEqual(titles, ["B's notification"])

    def test_user_a_cannot_mark_user_b_notification_read(self):
        with tenant_context(self.school):
            n = notify(recipient_user_id=self.other_user.id, title="B's notification")
        client = self._client_as(self.staff_user)
        resp = client.post(f"/api/notifications/{n.id}/read/", {}, HTTP_HOST=self.DOMAIN)
        self.assertEqual(resp.status_code, 404)
        with tenant_context(self.school):
            n.refresh_from_db()
            self.assertFalse(n.is_read)

    def test_mark_all_read_does_not_affect_other_users(self):
        with tenant_context(self.school):
            b_notification = notify(recipient_user_id=self.other_user.id, title="B's")
            notify(recipient_user_id=self.staff_user.id, title="A's")
        client = self._client_as(self.staff_user)
        client.post("/api/notifications/mark-all-read/", {}, HTTP_HOST=self.DOMAIN)
        with tenant_context(self.school):
            b_notification.refresh_from_db()
            self.assertFalse(b_notification.is_read)

    def test_cross_tenant_notification_id_not_accessible(self):
        with tenant_context(self.school2):
            cross_tenant_notification = Notification.objects.create(
                recipient_user_id=self.staff_user.id, title="Other tenant"
            )
        client = self._client_as(self.staff_user)
        resp = client.post(
            f"/api/notifications/{cross_tenant_notification.id}/read/", {}, HTTP_HOST=self.DOMAIN
        )
        self.assertEqual(resp.status_code, 404)

    def test_client_cannot_modify_recipient_user_id(self):
        """The serializer never accepts recipient_user_id as input, and
        there is no write endpoint besides the read-marking ones, which
        never touch recipient_user_id."""
        with tenant_context(self.school):
            n = notify(recipient_user_id=self.staff_user.id, title="A")
        client = self._client_as(self.staff_user)
        client.post(
            f"/api/notifications/{n.id}/read/",
            {"recipient_user_id": str(self.other_user.id)},
            HTTP_HOST=self.DOMAIN,
        )
        with tenant_context(self.school):
            n.refresh_from_db()
            self.assertEqual(n.recipient_user_id, self.staff_user.id)

    def test_client_cannot_modify_is_read_via_update_api(self):
        """No PATCH/PUT endpoint exists at all for Notification."""
        with tenant_context(self.school):
            n = notify(recipient_user_id=self.staff_user.id, title="A")
        client = self._client_as(self.staff_user)
        resp = client.patch(f"/api/notifications/{n.id}/", {"is_read": True}, HTTP_HOST=self.DOMAIN)
        self.assertEqual(resp.status_code, 404)

    def test_owner_can_access_own_inbox(self):
        client = self._client_as(self.owner_user)
        resp = client.get("/api/notifications/", HTTP_HOST=self.DOMAIN)
        self.assertEqual(resp.status_code, 200)

    def test_staff_can_access_own_inbox(self):
        client = self._client_as(self.staff_user)
        resp = client.get("/api/notifications/", HTTP_HOST=self.DOMAIN)
        self.assertEqual(resp.status_code, 200)

    def test_instructor_can_access_own_inbox(self):
        client = self._client_as(self.instructor_user)
        resp = client.get("/api/notifications/", HTTP_HOST=self.DOMAIN)
        self.assertEqual(resp.status_code, 200)

    def test_student_can_access_own_inbox(self):
        client = self._client_as(self.student_user)
        resp = client.get("/api/notifications/", HTTP_HOST=self.DOMAIN)
        self.assertEqual(resp.status_code, 200)

    def test_parent_can_access_own_inbox(self):
        client = self._client_as(self.parent_user)
        resp = client.get("/api/notifications/", HTTP_HOST=self.DOMAIN)
        self.assertEqual(resp.status_code, 200)

    def test_no_permission_required_for_any_role(self):
        """Confirms zero notification permissions exist and none are
        needed - every role above succeeded with only IsAuthenticated."""
        with tenant_context(self.school):
            from roles.models import Permission

            notif_permissions = Permission.objects.filter(module__icontains="notification")
            self.assertEqual(notif_permissions.count(), 0)
