"""System-role seeding: defaults apply once, at role creation; owner customizations survive.

``roles.signals.seed_default_roles`` is what the ``post_migrate`` receiver calls for every tenant
schema. These tests call it directly inside a tenant (no migration is run by the tests themselves;
creating the test tenant is the only place the real signal fires, and that is exactly the
"new tenant provisioning" case under test).

They create tenant schemas and need a disposable PostgreSQL database, so they are meant to be run
only in an explicitly authorized isolated test stage.
"""

from types import SimpleNamespace
from unittest import mock

from django.core.exceptions import ImproperlyConfigured
from django.db import connection
from django.test import TransactionTestCase
from django_tenants.utils import tenant_context

from organizations.models import Domain, Organization
from roles import signals
from roles.constants import SYSTEM_PERMISSIONS
from roles.models import Permission, Role

# The approved initial permission sets (literal on purpose: a change to the defaults must be a
# conscious change to this test as well).
STAFF_DEFAULTS = {
    "view_calendar_events", "manage_calendar_events", "view_admissions",
    "manage_admission_enquiries", "manage_admission_applications", "review_admission_documents",
    "review_admission_applications", "make_admission_decisions", "enroll_admitted_students",
    "view_own_leaves", "apply_staff_leave", "cancel_own_leave", "view_all_leaves",
    "manage_staff_leaves", "manage_leave_types", "view_ptm", "manage_ptm", "record_ptm_feedback",
    "record_interview_feedback", "report_exam_malpractice",
}
INSTRUCTOR_DEFAULTS = {
    "view_calendar_events", "view_admissions", "review_admission_applications",
    "view_own_leaves", "apply_staff_leave", "cancel_own_leave", "view_homework", "manage_homework",
    "view_ptm", "record_ptm_feedback", "record_interview_feedback", "report_exam_malpractice",
    "view_health_records",
}
STUDENT_DEFAULTS = {"view_own_fees", "pay_own_fees", "view_calendar_events", "view_own_homework"}
PARENT_DEFAULTS = {
    "view_own_children", "view_child_attendance", "view_child_timetable", "view_calendar_events",
    "view_child_homework", "view_child_ptm",
}
PARENT_NOT_DEFAULT = {"view_child_results", "view_child_fees", "pay_child_fees"}
ALL_CODENAMES = {p["codename"] for p in SYSTEM_PERMISSIONS}


def codenames(role):
    return set(role.permissions.values_list("codename", flat=True))


def snapshot():
    return {
        r.slug: (r.name, r.description, r.is_system_role, frozenset(codenames(r)))
        for r in Role.objects.all()
    }


class RoleSeedingTests(TransactionTestCase):
    SCHEMA = "role_seed_school"
    DOMAIN = "roleseed.localhost"

    def _cleanup(self):
        connection.set_schema_to_public()
        for school in Organization.objects.filter(schema_name=self.SCHEMA):
            school.delete(force_drop=True)

    def setUp(self):
        self.addCleanup(self._cleanup)
        self._cleanup()
        connection.set_schema_to_public()
        # Creating the tenant runs the real post_migrate seeding once: the "new tenant" case.
        self.school = Organization.objects.create(schema_name=self.SCHEMA, name="Role Seed School")
        Domain.objects.create(domain=self.DOMAIN, tenant=self.school, is_primary=True)

    # ---------------------------------------------------------------- initial defaults
    def test_new_tenant_receives_the_approved_defaults_exactly_once(self):
        with tenant_context(self.school):
            self.assertEqual(
                sorted(Role.objects.values_list("slug", flat=True)),
                ["instructor", "owner", "parent", "staff", "student"],
            )
            for slug in ("owner", "staff", "instructor", "student", "parent"):
                self.assertEqual(Role.objects.filter(slug=slug).count(), 1, slug)
                self.assertTrue(Role.objects.get(slug=slug).is_system_role, slug)

            self.assertEqual(codenames(Role.objects.get(slug="owner")), ALL_CODENAMES)
            self.assertEqual(codenames(Role.objects.get(slug="staff")), STAFF_DEFAULTS)
            self.assertEqual(codenames(Role.objects.get(slug="instructor")), INSTRUCTOR_DEFAULTS)
            self.assertEqual(codenames(Role.objects.get(slug="student")), STUDENT_DEFAULTS)

            parent = codenames(Role.objects.get(slug="parent"))
            self.assertEqual(parent, PARENT_DEFAULTS)
            self.assertFalse(parent & PARENT_NOT_DEFAULT)
            # Exact grants, not just a count: results, fee data and payments need owner opt-in.
            for codename in PARENT_NOT_DEFAULT:
                self.assertNotIn(codename, parent)

            # Every registered permission exists exactly once.
            self.assertEqual(Permission.objects.count(), len(ALL_CODENAMES))

    # ---------------------------------------------------------------- reseeding preserves edits
    def test_reseeding_does_not_restore_a_removed_permission(self):
        with tenant_context(self.school):
            parent = Role.objects.get(slug="parent")
            parent.permissions.remove(Permission.objects.get(codename="view_child_attendance"))
            self.assertEqual(signals.seed_default_roles(), [])
            self.assertEqual(
                codenames(Role.objects.get(slug="parent")), PARENT_DEFAULTS - {"view_child_attendance"}
            )

    def test_a_role_emptied_by_the_owner_stays_empty(self):
        with tenant_context(self.school):
            parent = Role.objects.get(slug="parent")
            parent.permissions.clear()
            self.assertEqual(signals.seed_default_roles(), [])
            self.assertEqual(codenames(Role.objects.get(slug="parent")), set())

    def test_owner_edits_to_names_descriptions_and_permissions_survive(self):
        with tenant_context(self.school):
            staff = Role.objects.get(slug="staff")
            staff.name, staff.description = "Office Team", "Customized by the school"
            staff.save()
            staff.permissions.set(Permission.objects.filter(codename__in=["view_own_leaves", "view_admissions"]))

            owner = Role.objects.get(slug="owner")
            owner.name, owner.description = "Principal", "Head of school"
            owner.save()
            owner.permissions.remove(*Permission.objects.filter(codename__in=["delete_role", "view_audit_log"]))

            before = snapshot()
            signals.seed_default_roles()
            after = snapshot()

            self.assertEqual(after, before)
            self.assertEqual(after["staff"][:2], ("Office Team", "Customized by the school"))
            self.assertEqual(after["staff"][3], frozenset({"view_own_leaves", "view_admissions"}))
            self.assertEqual(after["owner"][:2], ("Principal", "Head of school"))
            # The owner is not reset to "every permission" by a later seeding run.
            self.assertEqual(after["owner"][3], frozenset(ALL_CODENAMES - {"delete_role", "view_audit_log"}))

    def test_existing_roles_are_not_backfilled_with_defaults(self):
        with tenant_context(self.school):
            # An existing tenant: its parent role predates the new defaults and carries fewer grants.
            parent = Role.objects.get(slug="parent")
            parent.permissions.set(Permission.objects.filter(codename__in=["view_own_children"]))
            student = Role.objects.get(slug="student")
            student.permissions.clear()

            signals.seed_default_roles()

            self.assertEqual(codenames(Role.objects.get(slug="parent")), {"view_own_children"})
            self.assertEqual(codenames(Role.objects.get(slug="student")), set())

    def test_repeated_seeding_changes_nothing(self):
        with tenant_context(self.school):
            first = snapshot()
            self.assertEqual(signals.seed_default_roles(), [])
            second = snapshot()
            self.assertEqual(signals.seed_default_roles(), [])
            third = snapshot()
            self.assertEqual(first, second)
            self.assertEqual(second, third)
            self.assertEqual(Role.objects.count(), 5)

    def test_permission_labels_refresh_without_touching_grants(self):
        with tenant_context(self.school):
            perm = Permission.objects.get(codename="view_child_attendance")
            perm.name = "Edited label"
            perm.save()
            parent = Role.objects.get(slug="parent")
            parent.permissions.remove(perm)

            signals.seed_default_roles()

            perm.refresh_from_db()
            self.assertNotEqual(perm.name, "Edited label")  # the registry label is maintained
            self.assertNotIn("view_child_attendance", codenames(Role.objects.get(slug="parent")))  # grants are not

    # ---------------------------------------------------------------- creation of a missing role
    def test_a_missing_system_role_is_created_once_with_its_defaults(self):
        with tenant_context(self.school):
            Role.objects.filter(slug="parent").delete()

            self.assertEqual(signals.seed_default_roles(), ["parent"])
            parent = Role.objects.get(slug="parent")
            self.assertEqual((parent.name, parent.is_system_role), ("Parent", True))
            self.assertEqual(codenames(parent), PARENT_DEFAULTS)

            # Seeded exactly once: a second run neither recreates nor re-grants.
            parent.permissions.clear()
            self.assertEqual(signals.seed_default_roles(), [])
            self.assertEqual(codenames(Role.objects.get(slug="parent")), set())

    def test_an_unregistered_default_fails_loudly_and_leaves_no_half_seeded_role(self):
        broken = [dict(signals.SYSTEM_ROLES[-1], default_permissions=["view_own_children", "no_such_permission"])]
        with tenant_context(self.school):
            Role.objects.filter(slug="parent").delete()
            with mock.patch.object(signals, "SYSTEM_ROLES", broken):
                with self.assertRaises(ImproperlyConfigured):
                    signals.seed_default_roles()
            # The transaction rolled back: no role row that a later run would mistake for "existing".
            self.assertFalse(Role.objects.filter(slug="parent").exists())

    # ---------------------------------------------------------------- tenant/public safeguard
    def test_the_signal_never_seeds_the_public_schema(self):
        connection.set_schema_to_public()
        with mock.patch.object(signals, "seed_default_roles") as seed:
            signals.seed_roles(sender=SimpleNamespace(name="roles"))
            seed.assert_not_called()
        # And it ignores other apps' post_migrate events entirely.
        with tenant_context(self.school):
            with mock.patch.object(signals, "seed_default_roles") as seed:
                signals.seed_roles(sender=SimpleNamespace(name="students"))
                seed.assert_not_called()
                signals.seed_roles(sender=SimpleNamespace(name="roles"))
                seed.assert_called_once_with()
