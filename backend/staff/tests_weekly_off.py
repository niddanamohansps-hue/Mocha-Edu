"""The school's weekly off days are configurable (attendance settings) and used by the leave code.

Creates a tenant schema, so it needs a disposable PostgreSQL database.
"""
import uuid
from datetime import date
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import connection
from django.test import TransactionTestCase
from django_tenants.utils import tenant_context
from rest_framework.test import APIClient

from accounts.models import User
from attendance.models import AttendanceSettings, default_weekly_off_days, validate_weekly_off_days
from core.models import AuditLog
from organizations.models import Domain, Organization
from profiles.models import Profile
from roles.models import Role, UserRole

from .leave_services import calculate_working_days

D = Decimal
# 2026-03-02 is a Monday; so 03-06 is Friday, 03-07 Saturday, 03-08 Sunday.
MON, FRI, SAT, SUN = date(2026, 3, 2), date(2026, 3, 6), date(2026, 3, 7), date(2026, 3, 8)
NEXT_MON = date(2026, 3, 9)
URL = "/api/attendance/settings/"


class WeeklyOffFixture(TransactionTestCase):
    SCHEMA, DOMAIN = "weekly_off_s", "weekly-off.localhost"

    def _cleanup(self):
        connection.set_schema_to_public()
        for school in Organization.objects.filter(schema_name=self.SCHEMA):
            school.delete(force_drop=True)
        User.objects.filter(username__startswith="wk_").delete()

    def setUp(self):
        self.addCleanup(self._cleanup)
        self._cleanup()
        connection.set_schema_to_public()
        self.school = Organization.objects.create(schema_name=self.SCHEMA, name="Weekly off school")
        Domain.objects.create(domain=self.DOMAIN, tenant=self.school, is_primary=True)
        self.owner = User.objects.create_user(username="wk_owner", email="wk_owner@wk.test", password="Pass1234!")
        self.other = User.objects.create_user(username="wk_other", email="wk_other@wk.test", password="Pass1234!")
        with tenant_context(self.school):
            Profile.objects.create(user_id=self.owner.id, first_name="Owner", last_name="User")
            UserRole.objects.create(user=self.owner, role=Role.objects.get(slug="owner"))
            Profile.objects.create(user_id=self.other.id, first_name="Other", last_name="User")
            UserRole.objects.create(user=self.other, role=Role.objects.get(slug="staff"))

    def set_off(self, days):
        with tenant_context(self.school):
            settings_row = AttendanceSettings.get_solo()
            settings_row.weekly_off_days = days
            settings_row.save()

    def working(self, start, end, **kw):
        with tenant_context(self.school):
            return calculate_working_days(start, end, **kw)

    def call(self, user, method, data=None):
        client = APIClient()
        client.force_authenticate(user=user)
        return getattr(client, method)(URL, data, format="json", HTTP_HOST=self.DOMAIN)


class ValidationTests(TransactionTestCase):
    def test_valid_lists_are_accepted_and_sorted(self):
        self.assertEqual(validate_weekly_off_days([5]), [5])
        self.assertEqual(validate_weekly_off_days([6, 5]), [5, 6])
        self.assertEqual(validate_weekly_off_days([]), [])
        self.assertEqual(validate_weekly_off_days([0, 1, 2, 3, 4, 5]), [0, 1, 2, 3, 4, 5])

    def test_bad_lists_are_rejected(self):
        for label, value in {
            "not a list": "5", "a number": 5, "none": None, "dict": {"a": 1},
            "out of range": [7], "negative": [-1], "a float": [5.0], "a string": ["5"],
            "a boolean": [True], "duplicate": [5, 5], "every day": [0, 1, 2, 3, 4, 5, 6],
        }.items():
            with self.subTest(label), self.assertRaises(DjangoValidationError):
                validate_weekly_off_days(value)

    def test_the_default_is_sunday_as_before(self):
        self.assertEqual(default_weekly_off_days(), [6])


class WorkingDayTests(WeeklyOffFixture):
    def test_a_school_that_changed_nothing_keeps_sunday_off(self):
        with tenant_context(self.school):
            self.assertEqual(AttendanceSettings.weekly_off(), frozenset({6}))
            self.assertEqual(AttendanceSettings.objects.count(), 0)  # reading never writes
        self.assertEqual(self.working(MON, NEXT_MON), D("7"))  # Mon-Sat + Mon = 8 days minus Sunday 3-8

    def test_saturday_off_counts_saturday_but_not_sunday_differently(self):
        self.set_off([5])
        self.assertEqual(self.working(MON, NEXT_MON), D("7"))     # Mon-Fri, Sun, Mon: only Saturday is off
        self.assertEqual(self.working(SUN, SUN), D("1"))          # Sunday is now a working day
        with self.assertRaises(ValidationError):
            self.working(SAT, SAT)                                # Saturday has no working day in it

    def test_saturday_and_sunday_off(self):
        self.set_off([5, 6])
        self.assertEqual(self.working(MON, NEXT_MON), D("6"))     # Mon-Fri + Mon
        self.assertEqual(self.working(MON, FRI), D("5"))

    def test_friday_and_saturday_off(self):
        self.set_off([4, 5])
        self.assertEqual(self.working(MON, NEXT_MON), D("6"))     # Mon-Thu, Sun, Mon

    def test_no_weekly_off_at_all(self):
        self.set_off([])
        self.assertEqual(self.working(MON, NEXT_MON), D("8"))

    def test_a_range_made_only_of_off_days_is_refused(self):
        self.set_off([5, 6])
        with self.assertRaises(ValidationError):
            self.working(SAT, SUN)

    def test_half_days_follow_the_setting(self):
        self.set_off([5])
        with self.assertRaises(ValidationError):
            self.working(SAT, SAT, is_half_day=True)       # Saturday is off now
        self.assertEqual(self.working(SUN, SUN, is_half_day=True), D("0.5"))   # Sunday is a working day now
        self.set_off([6])
        self.assertEqual(self.working(SAT, SAT, is_half_day=True), D("0.5"))
        with self.assertRaises(ValidationError):
            self.working(SUN, SUN, is_half_day=True)

    def test_published_holidays_still_apply_on_top(self):
        from academics.models import CalendarEvent
        self.set_off([5])
        with tenant_context(self.school):
            CalendarEvent.objects.create(
                title="Holiday", event_type="HOLIDAY", is_holiday=True, status="PUBLISHED", start_date=MON, end_date=MON,
            )
        self.assertEqual(self.working(MON, FRI), D("4"))      # Mon-Fri minus the Monday holiday
        self.assertEqual(self.working(MON, NEXT_MON), D("6"))  # Tue-Fri, Sunday and the next Monday (Saturday is off)

    def test_the_setting_is_read_for_the_current_school_only(self):
        self.set_off([5])
        other = Organization.objects.create(schema_name="weekly_off_o", name="Other")
        Domain.objects.create(domain="weekly-off-o.localhost", tenant=other, is_primary=True)
        try:
            with tenant_context(other):
                self.assertEqual(AttendanceSettings.weekly_off(), frozenset({6}))
        finally:
            connection.set_schema_to_public()
            other.delete(force_drop=True)


class SettingsApiTests(WeeklyOffFixture):
    def test_reading_shows_the_default(self):
        resp = self.call(self.owner, "get")
        self.assertEqual((resp.status_code, resp.data["weekly_off_days"]), (200, [6]))

    def test_the_owner_can_change_it_and_it_takes_effect(self):
        resp = self.call(self.owner, "patch", {"weekly_off_days": [6, 5]})
        self.assertEqual((resp.status_code, resp.data["weekly_off_days"]), (200, [5, 6]))
        self.assertEqual(self.working(MON, NEXT_MON), D("6"))
        with tenant_context(self.school):
            self.assertEqual(AttendanceSettings.weekly_off(), frozenset({5, 6}))

    def test_bad_values_are_a_clean_400_and_change_nothing(self):
        self.call(self.owner, "patch", {"weekly_off_days": [5]})
        for bad in ("5", 5, [7], [-1], [5, 5], [True], ["5"], [0, 1, 2, 3, 4, 5, 6], None):
            with self.subTest(value=bad):
                self.assertEqual(self.call(self.owner, "patch", {"weekly_off_days": bad}).status_code, 400)
        self.assertEqual(self.call(self.owner, "get").data["weekly_off_days"], [5])

    def test_others_cannot_change_it(self):
        self.assertEqual(self.call(self.other, "patch", {"weekly_off_days": [5]}).status_code, 403)
        with tenant_context(self.school):
            self.assertEqual(AttendanceSettings.weekly_off(), frozenset({6}))

    def test_the_change_is_audit_logged(self):
        self.call(self.owner, "patch", {"weekly_off_days": [5]})
        with tenant_context(self.school):
            entry = AuditLog.objects.filter(action="attendance_settings_changed").latest("created_at")
            self.assertEqual((entry.changes["old_weekly_off_days"], entry.changes["new_weekly_off_days"]), ([6], [5]))

    def test_changing_other_settings_leaves_the_off_days_alone(self):
        self.call(self.owner, "patch", {"weekly_off_days": [5]})
        self.call(self.owner, "patch", {"lock_after_days": 3})
        self.assertEqual(self.call(self.owner, "get").data["weekly_off_days"], [5])
