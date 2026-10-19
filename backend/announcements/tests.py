import datetime
import uuid

from django.core.exceptions import ValidationError
from django.db import IntegrityError, connection, transaction
from django.db.models import ProtectedError
from django.test import SimpleTestCase, TransactionTestCase
from django.utils import timezone
from django_tenants.utils import tenant_context

from organizations.models import Domain, Organization

from .models import Announcement, AnnouncementRecipient

ANNOUNCEMENT_PERMISSIONS = {"view_announcements", "manage_announcements", "broadcast_announcements"}


def _announcement(**overrides):
    fields = {
        "title": "Sports Day",
        "body": "Sports day is on Friday.",
        "created_by_user_id": uuid.uuid4(),
        "audience_type": Announcement.AudienceType.ALL_STAFF,
    }
    fields.update(overrides)
    return Announcement(**fields)


class AnnouncementFixtureMixin:
    """Phase 1 smoke tests only - one isolated tenant in the test database."""

    SCHEMA_NAME = "announce_test_school"
    DOMAIN = "announcetest.localhost"

    def _cleanup(self):
        connection.set_schema_to_public()
        with connection.cursor() as cursor:
            cursor.execute(f'DROP SCHEMA IF EXISTS "{self.SCHEMA_NAME}" CASCADE')
        Organization.objects.filter(schema_name=self.SCHEMA_NAME).delete()

    def setUp(self):
        self.addCleanup(self._cleanup)
        self._cleanup()
        self.school = Organization.objects.create(schema_name=self.SCHEMA_NAME, name="Announce Test School")
        Domain.objects.create(domain=self.DOMAIN, tenant=self.school, is_primary=True)

    def tearDown(self):
        self._cleanup()


class AnnouncementModelSmokeTest(AnnouncementFixtureMixin, TransactionTestCase):
    def test_tables_exist_and_defaults_apply(self):
        with tenant_context(self.school):
            announcement = _announcement()
            announcement.full_clean()
            announcement.save()
            AnnouncementRecipient.objects.create(announcement=announcement, user_id=uuid.uuid4())

            saved = Announcement.objects.get(id=announcement.id)
            self.assertEqual(saved.status, Announcement.Status.DRAFT)
            self.assertFalse(saved.send_email)
            self.assertIsNone(saved.published_at)
            self.assertEqual(saved.recipients.count(), 1)

    def test_recipient_is_unique_per_announcement_and_user(self):
        with tenant_context(self.school):
            announcement = _announcement()
            announcement.save()
            user_id = uuid.uuid4()
            AnnouncementRecipient.objects.create(announcement=announcement, user_id=user_id)
            with self.assertRaises(IntegrityError), transaction.atomic():
                AnnouncementRecipient.objects.create(announcement=announcement, user_id=user_id)

    def test_announcement_permissions_are_seeded_and_owner_only(self):
        from roles.models import Permission, Role

        with tenant_context(self.school):
            seeded = set(
                Permission.objects.filter(codename__in=ANNOUNCEMENT_PERMISSIONS).values_list("codename", flat=True)
            )
            self.assertEqual(seeded, ANNOUNCEMENT_PERMISSIONS)

            owner_codenames = set(
                Role.objects.get(slug="owner").permissions.values_list("codename", flat=True)
            )
            self.assertTrue(ANNOUNCEMENT_PERMISSIONS <= owner_codenames)

            staff_codenames = set(
                Role.objects.get(slug="staff").permissions.values_list("codename", flat=True)
            )
            self.assertFalse(ANNOUNCEMENT_PERMISSIONS & staff_codenames)


class AnnouncementValidationSmokeTest(SimpleTestCase):
    """clean() checks only ids/values, so these need no saved Section/Level rows."""

    def assertCleanFails(self, announcement, field):
        with self.assertRaises(ValidationError) as ctx:
            announcement.clean()
        self.assertIn(field, ctx.exception.message_dict)

    def test_section_audience_requires_section_only(self):
        self.assertCleanFails(_announcement(audience_type=Announcement.AudienceType.SECTION), "audience_section")
        self.assertCleanFails(
            _announcement(
                audience_type=Announcement.AudienceType.SECTION,
                audience_section_id=uuid.uuid4(),
                audience_level_id=uuid.uuid4(),
            ),
            "audience_level",
        )

    def test_level_audience_requires_level_only(self):
        self.assertCleanFails(_announcement(audience_type=Announcement.AudienceType.LEVEL), "audience_level")

    def test_broad_audiences_reject_section_and_level(self):
        self.assertCleanFails(
            _announcement(audience_type=Announcement.AudienceType.ALL, audience_section_id=uuid.uuid4()),
            "audience_section",
        )

    def test_draft_without_scheduled_time_is_valid(self):
        _announcement().clean()

    def test_draft_with_future_scheduled_time_is_valid(self):
        _announcement(scheduled_at=timezone.now() + datetime.timedelta(days=1)).clean()

    def test_draft_with_past_scheduled_time_is_rejected(self):
        self.assertCleanFails(
            _announcement(scheduled_at=timezone.now() - datetime.timedelta(minutes=1)), "scheduled_at"
        )

    def test_scheduled_without_scheduled_time_is_rejected(self):
        self.assertCleanFails(_announcement(status=Announcement.Status.SCHEDULED), "scheduled_at")

    def test_scheduled_with_past_scheduled_time_is_rejected(self):
        self.assertCleanFails(
            _announcement(
                status=Announcement.Status.SCHEDULED, scheduled_at=timezone.now() - datetime.timedelta(minutes=1)
            ),
            "scheduled_at",
        )
        _announcement(
            status=Announcement.Status.SCHEDULED, scheduled_at=timezone.now() + datetime.timedelta(days=1)
        ).clean()

    def test_published_keeps_past_scheduled_time(self):
        _announcement(
            status=Announcement.Status.PUBLISHED,
            scheduled_at=timezone.now() - datetime.timedelta(days=1),
            published_at=timezone.now(),
        ).clean()


class AnnouncementPersistenceRulesTest(AnnouncementFixtureMixin, TransactionTestCase):
    def test_overdue_scheduled_announcement_update_is_rejected(self):
        with tenant_context(self.school):
            announcement = _announcement(
                status=Announcement.Status.SCHEDULED, scheduled_at=timezone.now() + datetime.timedelta(days=1)
            )
            announcement.save()
            # Simulate the scheduled time passing without publication; update()
            # deliberately bypasses save() to create that state.
            Announcement.objects.filter(id=announcement.id).update(
                scheduled_at=timezone.now() - datetime.timedelta(minutes=5)
            )
            overdue = Announcement.objects.get(id=announcement.id)
            overdue.title = "Edited title"
            with self.assertRaises(ValidationError) as ctx:
                overdue.save()
            self.assertIn("has passed", ctx.exception.message_dict["scheduled_at"][0])
            self.assertEqual(Announcement.objects.get(id=announcement.id).title, "Sports Day")

    def test_invalid_save_bypassing_serializer_is_rejected(self):
        with tenant_context(self.school):
            invalid = _announcement(audience_type=Announcement.AudienceType.SECTION)  # no section
            with self.assertRaises(ValidationError):
                invalid.save()
            self.assertEqual(Announcement.objects.count(), 0)

    def _academic_structure(self):
        from academics.models import AcademicLevel, Program, Section

        program = Program.objects.create(name="High School", code="HS")
        level = AcademicLevel.objects.create(program=program, name="Grade 10", order=10)
        section = Section.objects.create(level=level, name="A")
        return level, section

    def test_referenced_section_cannot_be_deleted(self):
        with tenant_context(self.school):
            _, section = self._academic_structure()
            _announcement(audience_type=Announcement.AudienceType.SECTION, audience_section=section).save()
            with self.assertRaises(ProtectedError), transaction.atomic():
                section.delete()

    def test_referenced_level_cannot_be_deleted(self):
        from academics.models import AcademicLevel

        with tenant_context(self.school):
            level, section = self._academic_structure()
            section.delete()  # leave only the announcement referencing the level
            _announcement(audience_type=Announcement.AudienceType.LEVEL, audience_level=level).save()
            with self.assertRaises(ProtectedError), transaction.atomic():
                level.delete()
            self.assertTrue(AcademicLevel.objects.filter(id=level.id).exists())


class AnnouncementTenantIsolationTest(AnnouncementFixtureMixin, TransactionTestCase):
    def test_announcements_are_not_visible_to_another_school(self):
        connection.set_schema_to_public()
        other_school = Organization.objects.create(schema_name="announce_test_school_b", name="Other School")
        Domain.objects.create(domain="announcetestb.localhost", tenant=other_school, is_primary=True)
        try:
            with tenant_context(self.school):
                announcement = _announcement()
                announcement.save()
                AnnouncementRecipient.objects.create(announcement=announcement, user_id=uuid.uuid4())

            with tenant_context(other_school):
                self.assertEqual(Announcement.objects.count(), 0)
                self.assertFalse(Announcement.objects.filter(id=announcement.id).exists())
                self.assertEqual(AnnouncementRecipient.objects.count(), 0)

            with tenant_context(self.school):
                self.assertEqual(Announcement.objects.count(), 1)
        finally:
            connection.set_schema_to_public()
            other_school.delete(force_drop=True)


# =============================================================================
# Phase 2-4: services, scheduled task, API
# =============================================================================

from unittest import mock  # noqa: E402

from kombu.exceptions import KombuError  # noqa: E402
from rest_framework.test import APIClient  # noqa: E402

from . import services  # noqa: E402
from .tasks import publish_due_announcements, publish_due_in_current_schema  # noqa: E402

PASSWORD = "Pass1234!"


class AnnouncementScenarioMixin(AnnouncementFixtureMixin):
    """
    One school with a small, deliberately awkward population:
    - student_a (section A, account with email)
    - student_b (section B, account with a blank email)
    - a section-A student with a profile but no linked account
    - a section-A withdrawn student (never a recipient)
    - parent (of student_a); the same account also has a second Profile as a
      staff member, so it must be deduplicated
    - a staff profile whose user_id has no accounts.User row
    - manager / viewer / broadcaster / plain staff / owner for API tests

    Giving a user the system 'staff' or 'owner' role auto-creates a
    StaffMember (profiles/signals.py), so user_plain and user_owner are
    genuinely staff and appear in staff audiences.
    """

    def setUp(self):
        super().setUp()
        from academics.models import AcademicLevel, Program, Section
        from accounts.models import User
        from families.models import Parent, StudentParentRelation
        from profiles.models import Profile
        from roles.models import Permission, Role, UserRole
        from staff.models import StaffMember
        from students.models import Student, StudentLevel

        def account(username, email):
            return User.objects.create_user(username=username, email=email, password=PASSWORD)

        self.user_a = account("ann_student_a", "ann_a@example.test")
        self.user_b = account("ann_student_b", "")
        self.user_parent = account("ann_parent", "ann_parent@example.test")
        self.user_manager = account("ann_manager", "ann_manager@example.test")
        self.user_viewer = account("ann_viewer", "ann_viewer@example.test")
        self.user_broadcaster = account("ann_broadcaster", "ann_broadcaster@example.test")
        self.user_plain = account("ann_plain", "ann_plain@example.test")
        self.user_owner = account("ann_owner", "ann_owner@example.test")
        self.ghost_user_id = uuid.uuid4()

        with tenant_context(self.school):
            program = Program.objects.create(name="High School", code="HS")
            self.level = AcademicLevel.objects.create(program=program, name="Grade 10", order=10)
            self.section_a = Section.objects.create(level=self.level, name="A")
            self.section_b = Section.objects.create(level=self.level, name="B")
            self.empty_section = Section.objects.create(level=self.level, name="Empty")

            def student(user_id, section, enrollment, status="active"):
                profile = Profile.objects.create(user_id=user_id, first_name="Stu", last_name=enrollment)
                record = Student.objects.create(profile=profile, enrollment_id=enrollment, status=status)
                StudentLevel.objects.create(
                    student=record, level=self.level, section=section, academic_year="2026-27", is_current=True
                )
                return record

            self.student_a = student(self.user_a.id, self.section_a, "ANN-A")
            student(self.user_b.id, self.section_b, "ANN-B")
            student(None, self.section_a, "ANN-C")
            student(uuid.uuid4(), self.section_a, "ANN-X", status="withdrawn")

            parent_profile = Profile.objects.create(user_id=self.user_parent.id, first_name="Par", last_name="Ent")
            parent = Parent.objects.create(profile=parent_profile)
            StudentParentRelation.objects.create(student=self.student_a, parent=parent, relation_type="mother")

            # Second Profile row for the same parent account (Profile.user_id is not unique).
            dup_profile = Profile.objects.create(user_id=self.user_parent.id, first_name="Par", last_name="Staff")
            StaffMember.objects.create(profile=dup_profile, employee_id="ANN-S1", designation="Clerk")
            ghost_profile = Profile.objects.create(user_id=self.ghost_user_id, first_name="Gho", last_name="St")
            StaffMember.objects.create(profile=ghost_profile, employee_id="ANN-S2", designation="Clerk")

            def role(slug, codenames):
                created = Role.objects.create(name=slug, slug=slug, is_system_role=False)
                created.permissions.set(Permission.objects.filter(codename__in=codenames))
                return created

            assignments = (
                (self.user_manager, role("ann-manager", ["view_announcements", "manage_announcements"])),
                (self.user_viewer, role("ann-viewer", ["view_announcements"])),
                (
                    self.user_broadcaster,
                    role("ann-broadcaster", ["view_announcements", "manage_announcements", "broadcast_announcements"]),
                ),
                (self.user_plain, Role.objects.get(slug="staff")),
                (self.user_owner, Role.objects.get(slug="owner")),
                (self.user_a, Role.objects.get(slug="student")),
                (self.user_b, Role.objects.get(slug="student")),
            )
            for user, assigned in assignments:
                UserRole.objects.create(user=user, role=assigned)

    def tearDown(self):
        from accounts.models import User

        super().tearDown()
        User.objects.filter(username__startswith="ann_").delete()

    def _staff_ids(self):
        # The parent account's second Profile, plus the auto-created staff records.
        return {self.user_parent.id, self.user_plain.id, self.user_owner.id}

    def _create(self, **overrides):
        with tenant_context(self.school):
            if "created_by_user_id" not in overrides:
                audience = overrides.get("audience_type", Announcement.AudienceType.ALL_STAFF)
                overrides["created_by_user_id"] = (
                    self.user_broadcaster.id
                    if audience == Announcement.AudienceType.ALL
                    else self.user_manager.id
                )
            announcement = _announcement(**overrides)
            announcement.save()
            return announcement

    def _counts(self, announcement_id):
        from notifications.models import EmailOutboxEvent, Notification

        with tenant_context(self.school):
            return {
                "recipients": AnnouncementRecipient.objects.filter(announcement_id=announcement_id).count(),
                "notifications": Notification.objects.filter(link=f"/dashboard/announcements/{announcement_id}").count(),
                "outbox": EmailOutboxEvent.objects.count(),
            }

    def _client(self, user):
        client = APIClient()
        resp = client.post("/api/auth/login/", {"username": user.username, "password": PASSWORD}, HTTP_HOST=self.DOMAIN)
        self.assertEqual(resp.status_code, 200, resp.content)
        return client

    def _api(self, client, method, path, data=None):
        return getattr(client, method)(f"/api/announcements/{path}", data, format="json", HTTP_HOST=self.DOMAIN)


class AnnouncementResolutionTest(AnnouncementScenarioMixin, TransactionTestCase):
    def test_each_audience_type_resolves_to_expected_accounts(self):
        A = Announcement.AudienceType
        expected = {
            A.SECTION: {self.user_a.id},
            A.LEVEL: {self.user_a.id, self.user_b.id},
            A.ALL_STUDENTS: {self.user_a.id, self.user_b.id},
            A.ALL_PARENTS: {self.user_parent.id},
            A.ALL_STAFF: self._staff_ids(),
            A.ALL: {self.user_a.id, self.user_b.id} | self._staff_ids(),
        }
        with tenant_context(self.school):
            for audience, user_ids in expected.items():
                with self.subTest(audience=audience):
                    extra = {}
                    if audience == A.SECTION:
                        extra["audience_section"] = self.section_a
                    if audience == A.LEVEL:
                        extra["audience_level"] = self.level
                    recipients = services.resolve_recipients(_announcement(audience_type=audience, **extra))
                    self.assertEqual(set(recipients), user_ids)

    def test_dedup_missing_accounts_and_blank_emails(self):
        with tenant_context(self.school):
            ids = services.resolve_recipient_user_ids(_announcement(audience_type=Announcement.AudienceType.ALL))
            recipients = services.resolve_recipients(_announcement(audience_type=Announcement.AudienceType.ALL))
        # The ghost id is a real Profile.user_id, so it is collected ...
        self.assertIn(self.ghost_user_id, ids)
        # ... but dropped once the shared account lookup finds no User.
        self.assertNotIn(self.ghost_user_id, recipients)
        # The parent account has two Profiles (parent + staff) but is one recipient.
        self.assertEqual(sorted(recipients), sorted({self.user_a.id, self.user_b.id} | self._staff_ids()))
        # A blank email stays an in-app recipient with no email address.
        self.assertIsNone(recipients[self.user_b.id])
        self.assertEqual(recipients[self.user_a.id], "ann_a@example.test")


class AnnouncementPublishServiceTest(AnnouncementScenarioMixin, TransactionTestCase):
    def test_publish_writes_snapshot_notifications_and_emails_once(self):
        announcement = self._create(audience_type=Announcement.AudienceType.ALL, send_email=True)
        with tenant_context(self.school):
            services.publish_announcement(announcement.id)
            published = Announcement.objects.get(id=announcement.id)
            self.assertEqual(published.status, Announcement.Status.PUBLISHED)
            self.assertIsNotNone(published.published_at)
            emailed = set(AnnouncementRecipient.objects.filter(email_sent=True).values_list("user_id", flat=True))
        self.assertEqual(emailed, {self.user_a.id} | self._staff_ids())  # user_b has a blank email
        self.assertEqual(self._counts(announcement.id), {"recipients": 5, "notifications": 5, "outbox": 4})

        with tenant_context(self.school), self.assertRaises(services.AnnouncementStateError):
            services.publish_announcement(announcement.id)
        self.assertEqual(self._counts(announcement.id), {"recipients": 5, "notifications": 5, "outbox": 4})

    def test_no_outbox_rows_when_email_disabled(self):
        announcement = self._create(audience_type=Announcement.AudienceType.ALL, send_email=False)
        with tenant_context(self.school):
            services.publish_announcement(announcement.id)
        self.assertEqual(self._counts(announcement.id), {"recipients": 5, "notifications": 5, "outbox": 0})

    def test_empty_audience_is_rejected_without_writes(self):
        announcement = self._create(
            audience_type=Announcement.AudienceType.SECTION, audience_section=self.empty_section, send_email=True
        )
        with tenant_context(self.school):
            with self.assertRaises(ValidationError) as ctx:
                services.publish_announcement(announcement.id)
            self.assertEqual(Announcement.objects.get(id=announcement.id).status, Announcement.Status.DRAFT)
        self.assertIn(services.EMPTY_AUDIENCE_MESSAGE, ctx.exception.messages)
        self.assertEqual(self._counts(announcement.id), {"recipients": 0, "notifications": 0, "outbox": 0})

    def test_failure_at_each_write_boundary_rolls_everything_back(self):
        for target in ("announcements.services.notify_many", "announcements.services.queue_email"):
            with self.subTest(failing=target):
                announcement = self._create(audience_type=Announcement.AudienceType.ALL, send_email=True)
                with tenant_context(self.school), mock.patch(target, side_effect=RuntimeError("boom")):
                    with self.assertRaises(RuntimeError):
                        services.publish_announcement(announcement.id)
                    reloaded = Announcement.objects.get(id=announcement.id)
                    self.assertEqual(reloaded.status, Announcement.Status.DRAFT)
                    self.assertIsNone(reloaded.published_at)
                self.assertEqual(self._counts(announcement.id), {"recipients": 0, "notifications": 0, "outbox": 0})

    def test_post_commit_dispatch_failure_keeps_publication(self):
        from notifications.models import EmailOutboxEvent
        from notifications.tasks import send_outbox_email

        announcement = self._create(
            audience_type=Announcement.AudienceType.SECTION, audience_section=self.section_a, send_email=True
        )
        with tenant_context(self.school), mock.patch.object(send_outbox_email, "delay", side_effect=KombuError("down")):
            services.publish_announcement(announcement.id)
            self.assertEqual(Announcement.objects.get(id=announcement.id).status, Announcement.Status.PUBLISHED)
            self.assertEqual(EmailOutboxEvent.objects.get().status, EmailOutboxEvent.Status.PENDING)
        self.assertEqual(self._counts(announcement.id), {"recipients": 1, "notifications": 1, "outbox": 1})

    def test_lifecycle_transitions(self):
        future = timezone.now() + datetime.timedelta(days=1)
        announcement = self._create(audience_type=Announcement.AudienceType.ALL_STUDENTS)
        with tenant_context(self.school):
            with self.assertRaises(services.AnnouncementStateError):
                services.cancel_schedule(announcement.id)
            with self.assertRaises(services.AnnouncementStateError):
                services.archive_announcement(announcement.id)
            with self.assertRaises(ValidationError):
                services.schedule_announcement(announcement.id, timezone.now() - datetime.timedelta(hours=1))

            self.assertEqual(
                services.schedule_announcement(announcement.id, future).status, Announcement.Status.SCHEDULED
            )
            cancelled = services.cancel_schedule(announcement.id)
            self.assertEqual((cancelled.status, cancelled.scheduled_at), (Announcement.Status.DRAFT, None))

            services.publish_announcement(announcement.id)
            with self.assertRaises(services.AnnouncementStateError):
                services.schedule_announcement(announcement.id, future)
            self.assertEqual(services.archive_announcement(announcement.id).status, Announcement.Status.ARCHIVED)
            with self.assertRaises(services.AnnouncementStateError):
                services.publish_announcement(announcement.id)


class AnnouncementScheduledTaskTest(AnnouncementScenarioMixin, TransactionTestCase):
    def _overdue(self, **overrides):
        announcement = self._create(
            status=Announcement.Status.SCHEDULED,
            scheduled_at=timezone.now() + datetime.timedelta(days=1),
            **overrides,
        )
        with tenant_context(self.school):
            # Simulate the clock passing the scheduled time.
            Announcement.objects.filter(id=announcement.id).update(
                scheduled_at=timezone.now() - datetime.timedelta(minutes=1)
            )
        return announcement

    def test_task_publishes_only_due_and_is_safe_to_repeat(self):
        due = self._overdue(audience_type=Announcement.AudienceType.ALL_STUDENTS)
        future = self._create(
            audience_type=Announcement.AudienceType.ALL_STUDENTS,
            status=Announcement.Status.SCHEDULED,
            scheduled_at=timezone.now() + datetime.timedelta(days=1),
        )
        draft = self._create(audience_type=Announcement.AudienceType.ALL_STUDENTS)
        empty = self._overdue(audience_type=Announcement.AudienceType.SECTION, audience_section=self.empty_section)

        with tenant_context(self.school):
            first = publish_due_in_current_schema(self.SCHEMA_NAME)
            second = publish_due_in_current_schema(self.SCHEMA_NAME)
            statuses = dict(Announcement.objects.values_list("id", "status"))
            reverted = Announcement.objects.get(id=empty.id)

        self.assertEqual(first, {"published": 1, "skipped": 0, "reverted": 1, "failed": 0, "deferred": 0})
        self.assertEqual(second, {"published": 0, "skipped": 0, "reverted": 0, "failed": 0, "deferred": 0})
        self.assertEqual(statuses[due.id], Announcement.Status.PUBLISHED)
        self.assertEqual(statuses[future.id], Announcement.Status.SCHEDULED)
        self.assertEqual(statuses[draft.id], Announcement.Status.DRAFT)
        self.assertEqual((reverted.status, reverted.scheduled_at), (Announcement.Status.DRAFT, None))
        self.assertEqual(self._counts(due.id)["recipients"], 2)

    def test_failures_retry_and_lost_races_are_skipped(self):
        due = self._overdue(audience_type=Announcement.AudienceType.ALL_STUDENTS)
        with tenant_context(self.school):
            with mock.patch("announcements.services.notify_many", side_effect=RuntimeError("db down")):
                self.assertEqual(publish_due_in_current_schema(self.SCHEMA_NAME)["failed"], 1)
            self.assertEqual(Announcement.objects.get(id=due.id).status, Announcement.Status.SCHEDULED)
            self.assertEqual(publish_due_in_current_schema(self.SCHEMA_NAME)["published"], 1)

        # Another worker published it first: this run skips it, writing nothing.
        again = self._overdue(audience_type=Announcement.AudienceType.ALL_STUDENTS)
        with tenant_context(self.school), mock.patch(
            "announcements.tasks.publish_announcement",
            side_effect=services.AnnouncementStateError("already published"),
        ):
            self.assertEqual(publish_due_in_current_schema(self.SCHEMA_NAME)["skipped"], 1)
        self.assertEqual(self._counts(due.id)["recipients"], 2)
        self.assertEqual(self._counts(again.id)["recipients"], 0)

    def test_one_failing_tenant_does_not_block_others(self):
        connection.set_schema_to_public()
        other = Organization.objects.create(schema_name="announce_test_school_b", name="Other School")
        Domain.objects.create(domain="announcetestb.localhost", tenant=other, is_primary=True)
        try:
            self._overdue(audience_type=Announcement.AudienceType.ALL_STUDENTS)
            real = publish_due_in_current_schema

            def flaky(schema_name, now=None, deadline=None):
                if schema_name == "announce_test_school_b":
                    raise RuntimeError("tenant broken")
                return real(schema_name, now, deadline)

            with mock.patch("announcements.tasks.publish_due_in_current_schema", side_effect=flaky):
                totals = publish_due_announcements()
            self.assertEqual(totals["tenant_errors"], 1)
            self.assertEqual(totals["published"], 1)
        finally:
            connection.set_schema_to_public()
            other.delete(force_drop=True)

    def test_scheduled_broadcast_reverts_to_draft_if_creator_loses_broadcast_permission(self):
        from core.models import AuditLog
        from roles.models import Role, UserRole

        due = self._overdue(
            audience_type=Announcement.AudienceType.ALL,
            created_by_user_id=self.user_broadcaster.id,
        )

        with tenant_context(self.school):
            # Demote broadcaster by revoking broadcast_announcements
            broadcaster_ur = UserRole.objects.get(user=self.user_broadcaster)
            plain_manager_role = Role.objects.create(name="plain-manager", slug="plain-manager", is_system_role=False)
            plain_manager_role.permissions.set(
                Role.objects.get(slug="ann-manager").permissions.all()
            )
            broadcaster_ur.role = plain_manager_role
            broadcaster_ur.save()

            res = publish_due_in_current_schema(self.SCHEMA_NAME)
            announcement = Announcement.objects.get(id=due.id)
            audit = AuditLog.objects.filter(model_name="Announcement", object_id=str(due.id)).first()

        self.assertEqual(res["reverted"], 1)
        self.assertEqual(res["published"], 0)
        self.assertEqual(announcement.status, Announcement.Status.DRAFT)
        self.assertIsNone(announcement.scheduled_at)
        self.assertIsNotNone(audit)
        self.assertEqual(audit.action, "announcement_schedule_cancelled")
        self.assertIn("broadcast_announcements", audit.changes["reason"])

    def test_scheduled_announcement_reverts_to_draft_if_creator_is_deactivated(self):
        due = self._overdue(
            audience_type=Announcement.AudienceType.ALL_STAFF,
            created_by_user_id=self.user_manager.id,
        )

        self.user_manager.is_active = False
        self.user_manager.save()
        try:
            with tenant_context(self.school):
                res = publish_due_in_current_schema(self.SCHEMA_NAME)
                announcement = Announcement.objects.get(id=due.id)

            self.assertEqual(res["reverted"], 1)
            self.assertEqual(res["published"], 0)
            self.assertEqual(announcement.status, Announcement.Status.DRAFT)
            self.assertIsNone(announcement.scheduled_at)
        finally:
            self.user_manager.is_active = True
            self.user_manager.save()

    def test_scheduled_announcement_reverts_to_draft_if_creator_has_no_tenant_role(self):
        due = self._overdue(
            audience_type=Announcement.AudienceType.ALL_STAFF,
            created_by_user_id=uuid.uuid4(),  # Ghost user not in tenant
        )

        with tenant_context(self.school):
            res = publish_due_in_current_schema(self.SCHEMA_NAME)
            announcement = Announcement.objects.get(id=due.id)

        self.assertEqual(res["reverted"], 1)
        self.assertEqual(res["published"], 0)
        self.assertEqual(announcement.status, Announcement.Status.DRAFT)
        self.assertIsNone(announcement.scheduled_at)

    def test_scheduled_announcement_publishes_normally_when_creator_authorized(self):
        due = self._overdue(
            audience_type=Announcement.AudienceType.ALL,
            created_by_user_id=self.user_broadcaster.id,
        )

        with tenant_context(self.school):
            res = publish_due_in_current_schema(self.SCHEMA_NAME)
            announcement = Announcement.objects.get(id=due.id)

        self.assertEqual(res["published"], 1)
        self.assertEqual(res["reverted"], 0)
        self.assertEqual(announcement.status, Announcement.Status.PUBLISHED)
        self.assertIsNotNone(announcement.published_at)


class AnnouncementApiTest(AnnouncementScenarioMixin, TransactionTestCase):
    def test_authentication_and_permissions(self):
        self.assertIn(self._api(APIClient(), "get", "").status_code, (401, 403))
        payload = {"title": "x", "body": "y", "audience_type": "all_staff"}

        plain = self._client(self.user_plain)
        self.assertEqual(self._api(plain, "get", "").status_code, 403)
        self.assertEqual(self._api(plain, "post", "", payload).status_code, 403)

        viewer = self._client(self.user_viewer)
        self.assertEqual(self._api(viewer, "get", "").status_code, 200)
        self.assertEqual(self._api(viewer, "post", "", payload).status_code, 403)

    def test_manager_draft_schedule_publish_flow(self):
        manager = self._client(self.user_manager)
        resp = self._api(manager, "post", "", {"title": "Exams", "body": "Next week", "audience_type": "section"})
        self.assertEqual(resp.status_code, 400)
        self.assertIn("audience_section", resp.data)

        resp = self._api(
            manager,
            "post",
            "",
            {
                "title": "Exams",
                "body": "Next week",
                "audience_type": "section",
                "audience_section": str(self.section_a.id),
                "status": "published",
                "created_by_user_id": str(uuid.uuid4()),
            },
        )
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(resp.data["status"], "draft")  # read-only fields are ignored
        self.assertEqual(resp.data["created_by_user_id"], str(self.user_manager.id))
        ann_id = resp.data["id"]

        self.assertEqual(self._api(manager, "patch", f"{ann_id}/", {"title": "Exams (updated)"}).status_code, 200)
        past = (timezone.now() - datetime.timedelta(hours=1)).isoformat()
        future = (timezone.now() + datetime.timedelta(days=1)).isoformat()
        self.assertEqual(self._api(manager, "post", f"{ann_id}/schedule/", {"scheduled_at": past}).status_code, 400)
        resp = self._api(manager, "post", f"{ann_id}/schedule/", {"scheduled_at": future})
        self.assertEqual(resp.data["status"], "scheduled")
        self.assertEqual(self._api(manager, "delete", f"{ann_id}/").status_code, 400)  # cancel first
        self.assertEqual(self._api(manager, "post", f"{ann_id}/cancel/").data["status"], "draft")

        resp = self._api(manager, "post", f"{ann_id}/publish/")
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual((resp.data["status"], resp.data["recipient_count"]), ("published", 1))
        self.assertEqual(self._api(manager, "post", f"{ann_id}/publish/").status_code, 400)
        self.assertEqual(self._api(manager, "patch", f"{ann_id}/", {"title": "nope"}).status_code, 400)

        resp = self._api(manager, "get", f"{ann_id}/recipients/")
        self.assertEqual([row["user_id"] for row in resp.data["results"]], [str(self.user_a.id)])

        self.assertEqual(self._api(manager, "delete", f"{ann_id}/").status_code, 204)  # archives
        self.assertEqual(self._api(manager, "get", f"{ann_id}/").data["status"], "archived")

        draft_id = self._api(manager, "post", "", {"title": "t", "body": "b", "audience_type": "all_staff"}).data["id"]
        self.assertEqual(self._api(manager, "delete", f"{draft_id}/").status_code, 204)
        self.assertEqual(self._api(manager, "get", f"{draft_id}/").status_code, 404)

    def test_empty_audience_returns_400(self):
        manager = self._client(self.user_manager)
        ann = self._create(audience_type=Announcement.AudienceType.SECTION, audience_section=self.empty_section)
        resp = self._api(manager, "post", f"{ann.id}/publish/")
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.data["non_field_errors"], [services.EMPTY_AUDIENCE_MESSAGE])

    def test_broadcast_requires_extra_permission(self):
        manager = self._client(self.user_manager)
        resp = self._api(manager, "post", "", {"title": "All", "body": "Everyone", "audience_type": "all"})
        self.assertEqual(resp.status_code, 201)
        ann_id = resp.data["id"]
        self.assertEqual(self._api(manager, "post", f"{ann_id}/publish/").status_code, 403)
        with tenant_context(self.school):
            self.assertEqual(Announcement.objects.get(id=ann_id).status, Announcement.Status.DRAFT)

        broadcaster = self._client(self.user_broadcaster)
        self.assertEqual(self._api(broadcaster, "post", f"{ann_id}/publish/").status_code, 200)

        owner_ann = self._create(audience_type=Announcement.AudienceType.ALL)
        owner = self._client(self.user_owner)
        self.assertEqual(self._api(owner, "post", f"{owner_ann.id}/publish/").status_code, 200)

    def test_broadcast_requires_extra_permission_on_schedule(self):
        manager = self._client(self.user_manager)
        resp = self._api(manager, "post", "", {"title": "All", "body": "Everyone", "audience_type": "all"})
        self.assertEqual(resp.status_code, 201)
        ann_id = resp.data["id"]

        future = (timezone.now() + datetime.timedelta(days=1)).isoformat()
        # Manager without broadcast_announcements must get 403 Forbidden on schedule
        resp = self._api(manager, "post", f"{ann_id}/schedule/", {"scheduled_at": future})
        self.assertEqual(resp.status_code, 403)
        with tenant_context(self.school):
            ann = Announcement.objects.get(id=ann_id)
            self.assertEqual(ann.status, Announcement.Status.DRAFT)
            self.assertIsNone(ann.scheduled_at)

        # Broadcaster role succeeds on schedule
        broadcaster = self._client(self.user_broadcaster)
        resp = self._api(broadcaster, "post", f"{ann_id}/schedule/", {"scheduled_at": future})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["status"], "scheduled")

        # Owner succeeds on schedule
        owner_ann = self._create(audience_type=Announcement.AudienceType.ALL)
        owner = self._client(self.user_owner)
        resp = self._api(owner, "post", f"{owner_ann.id}/schedule/", {"scheduled_at": future})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["status"], "scheduled")

    def test_changing_audience_on_scheduled_announcement_requires_cancel_first(self):
        manager = self._client(self.user_manager)
        resp = self._api(manager, "post", "", {"title": "Staff Meeting", "body": "Agenda", "audience_type": "all_staff"})
        self.assertEqual(resp.status_code, 201)
        ann_id = resp.data["id"]

        future = (timezone.now() + datetime.timedelta(days=1)).isoformat()
        # Schedule it as all_staff
        resp = self._api(manager, "post", f"{ann_id}/schedule/", {"scheduled_at": future})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["status"], "scheduled")

        # 1. Attempting to change audience to ALL via PATCH on scheduled announcement is rejected with 400
        resp = self._api(manager, "patch", f"{ann_id}/", {"audience_type": "all"})
        self.assertEqual(resp.status_code, 400)
        self.assertIn("non_field_errors", resp.data)
        self.assertEqual(
            resp.data["non_field_errors"],
            ["Changing the audience of a scheduled announcement requires cancelling the schedule first."],
        )

        # 2. Broadcaster also cannot mutate audience while scheduled (must cancel first)
        broadcaster = self._client(self.user_broadcaster)
        resp = self._api(broadcaster, "patch", f"{ann_id}/", {"audience_type": "all"})
        self.assertEqual(resp.status_code, 400)

        # 3. Cancel returns it to draft
        resp = self._api(manager, "post", f"{ann_id}/cancel/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["status"], "draft")

        # 4. In draft, updating audience to ALL succeeds
        resp = self._api(manager, "patch", f"{ann_id}/", {"audience_type": "all"})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["audience_type"], "all")

        # 5. But manager cannot schedule this draft because audience is ALL (requires broadcast_announcements)
        resp = self._api(manager, "post", f"{ann_id}/schedule/", {"scheduled_at": future})
        self.assertEqual(resp.status_code, 403)

        # 6. Broadcaster can schedule it
        resp = self._api(broadcaster, "post", f"{ann_id}/schedule/", {"scheduled_at": future})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["status"], "scheduled")

    def test_editing_scheduled_broadcast_requires_broadcast_permission(self):
        # A broadcast scheduled for ALL by owner
        owner = self._client(self.user_owner)
        resp = self._api(owner, "post", "", {"title": "School Closed", "body": "Weather alert", "audience_type": "all"})
        self.assertEqual(resp.status_code, 201)
        ann_id = resp.data["id"]

        future = (timezone.now() + datetime.timedelta(days=1)).isoformat()
        resp = self._api(owner, "post", f"{ann_id}/schedule/", {"scheduled_at": future})
        self.assertEqual(resp.status_code, 200)

        # Manager without broadcast_announcements cannot edit content of a scheduled ALL announcement
        manager = self._client(self.user_manager)
        resp = self._api(manager, "patch", f"{ann_id}/", {"title": "Tampered Title"})
        self.assertEqual(resp.status_code, 403)

        # Broadcaster with broadcast_announcements can edit content of scheduled ALL announcement
        broadcaster = self._client(self.user_broadcaster)
        resp = self._api(broadcaster, "patch", f"{ann_id}/", {"title": "Approved Title Edit"})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["title"], "Approved Title Edit")

    def test_scheduled_at_is_read_only_on_create_and_patch(self):
        manager = self._client(self.user_manager)
        future = (timezone.now() + datetime.timedelta(days=2)).isoformat()
        resp = self._api(
            manager,
            "post",
            "",
            {"title": "Draft", "body": "Body", "audience_type": "all_staff", "scheduled_at": future},
        )
        self.assertEqual(resp.status_code, 201)
        # scheduled_at must be ignored on direct create
        self.assertIsNone(resp.data["scheduled_at"])
        self.assertEqual(resp.data["status"], "draft")
        ann_id = resp.data["id"]

        with tenant_context(self.school):
            self.assertIsNone(Announcement.objects.get(id=ann_id).scheduled_at)

        # Attempting to mutate scheduled_at via PATCH must be ignored
        resp = self._api(manager, "patch", f"{ann_id}/", {"scheduled_at": future, "title": "Updated"})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["title"], "Updated")
        self.assertIsNone(resp.data["scheduled_at"])

        with tenant_context(self.school):
            self.assertIsNone(Announcement.objects.get(id=ann_id).scheduled_at)

    def test_public_schema_returns_404_for_all_users_including_superuser(self):
        # 1. Anonymous user on public domain returns 404
        client = APIClient()
        resp = client.get("/api/announcements/", HTTP_HOST="localhost")
        self.assertEqual(resp.status_code, 404)

        # 2. Ordinary user on public domain returns 404
        plain = self._client(self.user_plain)
        resp = plain.get("/api/announcements/", HTTP_HOST="localhost")
        self.assertEqual(resp.status_code, 404)

        # 3. Superuser on public domain returns 404 (and does NOT crash with 500)
        from accounts.models import User
        super_user = User.objects.create_superuser(username="ann_super", email="super@example.test", password=PASSWORD)
        try:
            super_client = APIClient()
            resp = super_client.post("/api/auth/login/", {"username": super_user.username, "password": PASSWORD}, HTTP_HOST=self.DOMAIN)
            self.assertEqual(resp.status_code, 200)
            resp = super_client.get("/api/announcements/", HTTP_HOST="localhost")
            self.assertEqual(resp.status_code, 404)
            self.assertEqual(super_client.post("/api/announcements/", {"title": "X"}, HTTP_HOST="localhost").status_code, 404)
        finally:
            super_user.delete()

    def test_mine_uses_snapshot_and_hides_others(self):
        from students.models import StudentLevel

        ann = self._create(audience_type=Announcement.AudienceType.SECTION, audience_section=self.section_a)
        with tenant_context(self.school):
            services.publish_announcement(ann.id)
            # Moving the student after publication must not change what they saw.
            StudentLevel.objects.filter(student=self.student_a).update(section=self.section_b)
        self._create(audience_type=Announcement.AudienceType.SECTION, audience_section=self.section_a)

        student_a = self._client(self.user_a)
        resp = self._api(student_a, "get", "mine/")
        self.assertEqual([item["id"] for item in resp.data["results"]], [str(ann.id)])
        self.assertNotIn("audience_type", resp.data["results"][0])
        self.assertEqual(self._api(self._client(self.user_b), "get", "mine/").data["results"], [])
        # Students hold no view permission, so the admin list stays closed to them.
        self.assertEqual(self._api(student_a, "get", "").status_code, 403)

    def test_mine_detail_only_for_recipients_of_published(self):
        ann = self._create(audience_type=Announcement.AudienceType.SECTION, audience_section=self.section_a)
        draft = self._create(audience_type=Announcement.AudienceType.SECTION, audience_section=self.section_a)
        with tenant_context(self.school):
            services.publish_announcement(ann.id)

        student_a = self._client(self.user_a)
        resp = self._api(student_a, "get", f"mine/{ann.id}/")
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(set(resp.data), {"id", "title", "body", "published_at"})

        # Non-recipient, unpublished and unknown ids are all indistinguishable 404s.
        self.assertEqual(self._api(self._client(self.user_b), "get", f"mine/{ann.id}/").status_code, 404)
        self.assertEqual(self._api(student_a, "get", f"mine/{draft.id}/").status_code, 404)
        self.assertEqual(self._api(student_a, "get", f"mine/{uuid.uuid4()}/").status_code, 404)
        self.assertIn(self._api(APIClient(), "get", f"mine/{ann.id}/").status_code, (401, 403))

        # Archived announcements are no longer readable by recipients.
        with tenant_context(self.school):
            services.archive_announcement(ann.id)
        self.assertEqual(self._api(student_a, "get", f"mine/{ann.id}/").status_code, 404)

    def test_cross_tenant_ids_are_not_found(self):
        connection.set_schema_to_public()
        other = Organization.objects.create(schema_name="announce_test_school_b", name="Other School")
        Domain.objects.create(domain="announcetestb.localhost", tenant=other, is_primary=True)
        try:
            with tenant_context(other):
                foreign = _announcement(audience_type=Announcement.AudienceType.ALL_STAFF)
                foreign.save()
            owner = self._client(self.user_owner)
            for method, path in (
                ("get", f"{foreign.id}/"),
                ("post", f"{foreign.id}/publish/"),
                ("get", f"{foreign.id}/recipients/"),
                ("delete", f"{foreign.id}/"),
            ):
                with self.subTest(path=path):
                    self.assertEqual(self._api(owner, method, path).status_code, 404)
        finally:
            connection.set_schema_to_public()
            other.delete(force_drop=True)

    def test_protected_section_delete_returns_400(self):
        from academics.models import Section

        self._create(audience_type=Announcement.AudienceType.SECTION, audience_section=self.section_a)
        owner = self._client(self.user_owner)
        resp = owner.delete(f"/api/academics/sections/{self.section_a.id}/", HTTP_HOST=self.DOMAIN)
        self.assertEqual(resp.status_code, 400)
        self.assertIn("cannot be deleted", resp.data["non_field_errors"][0])
        with tenant_context(self.school):
            self.assertTrue(Section.objects.filter(id=self.section_a.id).exists())


class AnnouncementBeatScheduleTest(SimpleTestCase):
    def test_publish_due_announcements_is_scheduled_every_five_minutes(self):
        from django.conf import settings

        entry = settings.CELERY_BEAT_SCHEDULE["publish-due-announcements"]
        self.assertEqual(entry["task"], publish_due_announcements.name)
        self.assertEqual(entry["task"], "announcements.tasks.publish_due_announcements")
        self.assertEqual(entry["schedule"], datetime.timedelta(minutes=5))
        self.assertNotIn("options", entry)  # inherits the default queue


class AnnouncementConcurrencyTest(AnnouncementScenarioMixin, TransactionTestCase):
    """Real parallel PostgreSQL transactions (one connection per thread) on the
    isolated test database. Threads are released together by a barrier, so the
    row lock in services._locked() is genuinely contended."""

    def _race(self, *callables):
        """Runs each callable in its own thread/connection; returns ("ok", value)
        or ("err", exception) per callable, in order."""
        import threading

        barrier = threading.Barrier(len(callables))
        results = [None] * len(callables)

        def runner(index, fn):
            try:
                with tenant_context(self.school):
                    barrier.wait(timeout=30)
                    try:
                        results[index] = ("ok", fn())
                    except Exception as exc:  # noqa: BLE001 - the outcome is the assertion
                        results[index] = ("err", exc)
            finally:
                connection.close()

        threads = [threading.Thread(target=runner, args=(i, fn)) for i, fn in enumerate(callables)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=120)
            self.assertFalse(thread.is_alive(), "worker thread hung")
        return results

    def _status(self, announcement_id):
        with tenant_context(self.school):
            return Announcement.objects.get(id=announcement_id).status

    def test_concurrent_publishes_apply_side_effects_exactly_once(self):
        ann = self._create(audience_type=Announcement.AudienceType.ALL_STAFF, send_email=True)
        results = self._race(*[lambda: services.publish_announcement(ann.id) for _ in range(4)])

        winners = [r for r in results if r[0] == "ok"]
        losers = [r for r in results if r[0] == "err"]
        self.assertEqual(len(winners), 1, results)
        for _, exc in losers:
            self.assertIsInstance(exc, services.AnnouncementStateError)

        counts = self._counts(ann.id)
        self.assertEqual(counts["recipients"], counts["notifications"])
        self.assertGreater(counts["recipients"], 0)
        with tenant_context(self.school):
            from notifications.models import EmailOutboxEvent

            emailed = AnnouncementRecipient.objects.filter(announcement_id=ann.id, email_sent=True).count()
            self.assertEqual(EmailOutboxEvent.objects.count(), emailed)
            self.assertEqual(
                AnnouncementRecipient.objects.filter(announcement_id=ann.id).values("user_id").distinct().count(),
                counts["recipients"],
            )
        self.assertEqual(self._status(ann.id), Announcement.Status.PUBLISHED)

    def test_concurrent_publish_and_cancel_leave_a_consistent_state(self):
        ann = self._create(audience_type=Announcement.AudienceType.ALL_STAFF)
        with tenant_context(self.school):
            services.schedule_announcement(ann.id, timezone.now() + datetime.timedelta(hours=1))

        results = self._race(
            lambda: services.publish_announcement(ann.id),
            lambda: services.cancel_schedule(ann.id),
        )
        publish_result, cancel_result = results
        final = self._status(ann.id)
        counts = self._counts(ann.id)

        # Two serial orders are valid. cancel->publish: both succeed (a draft is
        # publishable). publish->cancel: cancel fails (a published announcement
        # is not scheduled). Either way the end state is PUBLISHED with exactly
        # one set of side effects, and any failure is a clean state error.
        self.assertEqual(publish_result[0], "ok", results)
        if cancel_result[0] == "err":
            self.assertIsInstance(cancel_result[1], ValidationError)
        self.assertEqual(final, Announcement.Status.PUBLISHED)
        self.assertGreater(counts["recipients"], 0)
        self.assertEqual(counts["recipients"], counts["notifications"])

    def test_concurrent_schedule_and_cancel_end_in_a_valid_state(self):
        ann = self._create(audience_type=Announcement.AudienceType.ALL_STAFF)
        when = timezone.now() + datetime.timedelta(hours=1)
        with tenant_context(self.school):
            services.schedule_announcement(ann.id, when)

        results = self._race(
            lambda: services.schedule_announcement(ann.id, when + datetime.timedelta(hours=1)),
            lambda: services.cancel_schedule(ann.id),
        )
        for outcome, value in results:
            if outcome == "err":
                self.assertIsInstance(value, ValidationError)
        with tenant_context(self.school):
            row = Announcement.objects.get(id=ann.id)
        self.assertIn(row.status, (Announcement.Status.SCHEDULED, Announcement.Status.DRAFT))
        # The row never ends up half-transitioned: scheduled has a time, draft does not.
        if row.status == Announcement.Status.SCHEDULED:
            self.assertIsNotNone(row.scheduled_at)
        else:
            self.assertIsNone(row.scheduled_at)
        self.assertEqual(self._counts(ann.id)["recipients"], 0)

    def test_two_workers_running_the_scheduled_task_publish_once(self):
        from .tasks import publish_due_in_current_schema

        ann = self._create(audience_type=Announcement.AudienceType.ALL_STAFF)
        with tenant_context(self.school):
            services.schedule_announcement(ann.id, timezone.now() + datetime.timedelta(minutes=5))
        later = timezone.now() + datetime.timedelta(minutes=10)

        results = self._race(
            lambda: publish_due_in_current_schema(self.school.schema_name, now=later),
            lambda: publish_due_in_current_schema(self.school.schema_name, now=later),
        )
        for outcome, value in results:
            self.assertEqual(outcome, "ok", value)
        self.assertEqual(sum(value["published"] for _, value in results), 1, results)
        self.assertEqual(sum(value["failed"] for _, value in results), 0, results)
        counts = self._counts(ann.id)
        self.assertGreater(counts["recipients"], 0)
        self.assertEqual(counts["recipients"], counts["notifications"])
        self.assertEqual(self._status(ann.id), Announcement.Status.PUBLISHED)
