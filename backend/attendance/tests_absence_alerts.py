"""Alerts Stage 3: absence alerts (``attendance.alerts``).

Creates tenant schemas and commits real transactions (the alert runs on commit), so it needs a
disposable PostgreSQL database.
"""
import datetime
from unittest import mock

from django.db import connection
from django.test import TransactionTestCase
from django_tenants.utils import tenant_context

from accounts.models import User
from families.models import Parent, StudentParentRelation
from fees.reminders import alert_today
from notifications.models import AlertLog, EmailOutboxEvent, Notification, NotificationSettings
from profiles.models import Profile
from students.models import Student, StudentLevel

from . import alerts
from .models import AttendanceSession, StudentAttendance
from .tests import AttendanceFixtureMixin

SESSIONS = "/api/attendance/sessions/"


class AbsenceAlertFixture(AttendanceFixtureMixin, TransactionTestCase):
    def setUp(self):
        super().setUp()
        connection.set_schema_to_public()
        self.parent_user = User.objects.create_user(
            username="att_parent", email="att_parent@atttest.com", password="Pass1234!"
        )
        with tenant_context(self.school):
            parent = Parent.objects.create(
                profile=Profile.objects.create(user_id=self.parent_user.id, first_name="Pam", last_name="Parent")
            )
            # student2 has no portal account of their own; the parent is the only recipient.
            StudentParentRelation.objects.create(student=self.student2, parent=parent, relation_type="guardian")
        self.today = alert_today()

    def _enable(self, on=True):
        with tenant_context(self.school):
            NotificationSettings.objects.update_or_create(singleton=True, defaults={"absence_alerts_enabled": on})

    def _post(self, statuses, day=None):
        """Mark the register as the instructor. ``statuses`` is {student: status}."""
        payload = {
            "section": str(self.section_a.id),
            "date": (day or self.today).isoformat(),
            "records": [{"student": str(s.id), "status": st} for s, st in statuses.items()],
        }
        return self._client_as(self.instructor_user).post(SESSIONS, payload, HTTP_HOST=self.DOMAIN, format="json")

    def _alerts(self):
        with tenant_context(self.school):
            return list(AlertLog.objects.filter(kind=AlertLog.Kind.ABSENCE).order_by("created_at"))


class SwitchAndRecipientTests(AbsenceAlertFixture):
    def test_nothing_is_sent_until_the_school_switches_it_on(self):
        resp = self._post({self.student1: "present", self.student2: "absent"})
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(self._alerts(), [])
        with tenant_context(self.school):
            self.assertEqual(Notification.objects.count(), 0)

    def test_an_absent_student_alerts_the_linked_parent_only_once_enabled(self):
        self._enable()
        self.assertEqual(self._post({self.student1: "present", self.student2: "absent"}).status_code, 201)
        found = self._alerts()
        self.assertEqual([a.recipient_user_id for a in found], [self.parent_user.id])
        self.assertEqual(found[0].student_id, self.student2.id)
        with tenant_context(self.school):
            note = Notification.objects.get()
            self.assertEqual(note.recipient_user_id, self.parent_user.id)
            self.assertIn("Alex Second", note.title)
            self.assertIn(self.today.strftime("%d %b %Y"), note.title)
            self.assertEqual(EmailOutboxEvent.objects.count(), 1)

    def test_the_students_own_account_is_alerted_too(self):
        self._enable()
        self._post({self.student1: "absent", self.student2: "present"})
        self.assertEqual([a.recipient_user_id for a in self._alerts()], [self.student_user.id])

    def test_present_late_half_day_and_leave_never_alert(self):
        self._enable()
        self._post({self.student1: "late", self.student2: "half_day"})
        self._post({self.student1: "leave", self.student2: "present"})
        self.assertEqual(self._alerts(), [])

    def test_a_student_with_no_account_and_no_parent_is_counted_not_alerted(self):
        self._enable()
        with tenant_context(self.school):
            lonely = Student.objects.create(
                profile=Profile.objects.create(first_name="Lone", last_name="Wolf"), enrollment_id="ENR-ATT-9", status="active"
            )
            session = AttendanceSession.objects.create(
                section=self.section_a, date=self.today, academic_year="2026"
            )
            StudentAttendance.objects.create(session=session, student=lonely, status="absent")
            summary = alerts.send_absence_alerts_for_session(session.id)
        self.assertEqual((summary["absent"], summary["no_recipient"], summary["sent"]), (1, 1, 0))

    def test_an_inactive_student_is_not_alerted(self):
        self._enable()
        with tenant_context(self.school):
            session = AttendanceSession.objects.create(
                section=self.section_a, date=self.today, academic_year="2026"
            )
            StudentAttendance.objects.create(session=session, student=self.withdrawn_student, status="absent")
            summary = alerts.send_absence_alerts_for_session(session.id)
        self.assertEqual(summary["absent"], 0)
        self.assertEqual(self._alerts(), [])


class RepeatAndTimingTests(AbsenceAlertFixture):
    def test_saving_the_same_register_again_sends_nothing_new(self):
        self._enable()
        self._post({self.student2: "absent"})
        self._post({self.student2: "absent"})
        self.assertEqual(len(self._alerts()), 1)
        with tenant_context(self.school):
            self.assertEqual(Notification.objects.count(), 1)

    def test_correcting_present_to_absent_later_sends_then(self):
        self._enable()
        resp = self._post({self.student1: "present", self.student2: "present"})
        self.assertEqual(self._alerts(), [])
        session_id = resp.data["id"]
        patch = self._client_as(self.instructor_user).patch(
            f"{SESSIONS}{session_id}/", {"records": [{"student": str(self.student2.id), "status": "absent"}]},
            HTTP_HOST=self.DOMAIN, format="json",
        )
        self.assertEqual(patch.status_code, 200, patch.data)
        self.assertEqual([a.recipient_user_id for a in self._alerts()], [self.parent_user.id])

    def test_correcting_absent_to_present_does_not_take_the_alert_back(self):
        self._enable()
        resp = self._post({self.student2: "absent"})
        self._client_as(self.instructor_user).patch(
            f"{SESSIONS}{resp.data['id']}/", {"records": [{"student": str(self.student2.id), "status": "present"}]},
            HTTP_HOST=self.DOMAIN, format="json",
        )
        self.assertEqual(len(self._alerts()), 1)

    def test_an_old_register_does_not_alert(self):
        self._enable()
        old = self.today - datetime.timedelta(days=alerts.MAX_AGE_DAYS + 1)
        self.assertEqual(self._post({self.student2: "absent"}, day=old).status_code, 201)
        self.assertEqual(self._alerts(), [])

    def test_a_register_from_two_days_ago_still_alerts(self):
        self._enable()
        recent = self.today - datetime.timedelta(days=alerts.MAX_AGE_DAYS)
        self._post({self.student2: "absent"}, day=recent)
        self.assertEqual(len(self._alerts()), 1)

    def test_the_school_calendar_day_is_used(self):
        self._enable()
        with tenant_context(self.school):
            session = AttendanceSession.objects.create(section=self.section_a, date=datetime.date(2026, 3, 10), academic_year="2026")
            StudentAttendance.objects.create(session=session, student=self.student2, status="absent")
            too_late = alerts.send_absence_alerts_for_session(session.id, today=datetime.date(2026, 3, 13))
            in_time = alerts.send_absence_alerts_for_session(session.id, today=datetime.date(2026, 3, 12))
        self.assertEqual(too_late["sent"], 0)
        self.assertEqual(in_time["sent"], 1)


class SafetyTests(AbsenceAlertFixture):
    def test_a_failing_alert_never_breaks_saving_the_register(self):
        self._enable()
        with mock.patch("attendance.alerts.send_absence_alerts_for_session", side_effect=RuntimeError("boom")):
            resp = self._post({self.student2: "absent"})
        self.assertEqual(resp.status_code, 201, resp.data)
        with tenant_context(self.school):
            self.assertEqual(StudentAttendance.objects.filter(student=self.student2, status="absent").count(), 1)

    def test_nothing_is_sent_for_a_register_that_was_rejected(self):
        self._enable()
        resp = self._client_as(self.unassigned_instructor_user).post(
            SESSIONS,
            {"section": str(self.section_a.id), "date": self.today.isoformat(),
             "records": [{"student": str(self.student2.id), "status": "absent"}]},
            HTTP_HOST=self.DOMAIN, format="json",
        )
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(self._alerts(), [])

    def test_a_public_schema_call_is_refused(self):
        connection.set_schema_to_public()
        with self.assertRaises(RuntimeError):
            alerts.send_absence_alerts_for_session("00000000-0000-0000-0000-000000000000")
