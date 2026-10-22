"""Alerts Stage 2: fee "due soon" / "overdue" reminders (``fees.reminders`` + ``fees.tasks``).

Creates tenant schemas, so it needs a disposable PostgreSQL database. "Today" is injected, never
read from the clock, except in the time-zone tests that pin the clock itself.
"""
import json
import time
from datetime import date, datetime, timedelta, timezone as dt_timezone
from decimal import Decimal
from unittest import mock

from django.conf import settings
from django.db import connection
from django.test import TransactionTestCase, override_settings
from django_tenants.utils import tenant_context

from accounts.models import User
from families.models import Parent, StudentParentRelation
from notifications.models import AlertLog, EmailOutboxEvent, Notification, NotificationSettings
from organizations.models import Domain, Organization
from profiles.models import Profile
from students.models import Student

from . import reminders, tasks
from .models import FeeHead, StudentFee
from .services import assign_student_fee, cancel_student_fee, record_payment

DUE = date(2026, 3, 20)


class ReminderFixture(TransactionTestCase):
    SCHEMA_A, SCHEMA_B = "fee_rem_a", "fee_rem_b"

    def _cleanup(self):
        connection.set_schema_to_public()
        for school in Organization.objects.filter(schema_name__in=[self.SCHEMA_A, self.SCHEMA_B]):
            school.delete(force_drop=True)
        User.objects.filter(username__startswith="frm_").delete()

    def _school(self, schema):
        connection.set_schema_to_public()
        school = Organization.objects.create(schema_name=schema, name=schema)
        Domain.objects.create(domain=f"{schema.replace('_', '-')}.localhost", tenant=school, is_primary=True)
        return school

    def _user(self, name, email=True):
        connection.set_schema_to_public()
        return User.objects.create_user(
            username=f"frm_{name}", email=f"frm_{name}@rem.test" if email else "", password="Pass1234!"
        )

    def _student(self, school, enrollment, *, user=None, status="active"):
        with tenant_context(school):
            profile = Profile.objects.create(
                user_id=user.id if user else None, first_name=f"First{enrollment}", last_name="Last"
            )
            return Student.objects.create(profile=profile, enrollment_id=enrollment, status=status)

    def _parent(self, school, student, user):
        with tenant_context(school):
            parent = Parent.objects.create(profile=Profile.objects.create(user_id=user.id, first_name="Par", last_name="Ent"))
            StudentParentRelation.objects.create(student=student, parent=parent, relation_type="guardian")

    def _fee(self, school, student, *, due=DUE, amount="1500.00", head=None):
        with tenant_context(school):
            head = head or FeeHead.objects.get_or_create(name="Tuition")[0]
            return assign_student_fee(
                student=student, fee_head=head, academic_year="2026", amount_due=Decimal(amount), due_date=due
            )

    def _pay(self, school, fee, amount):
        with tenant_context(school):
            fee = StudentFee.objects.get(pk=fee.pk)
            record_payment(
                student=fee.student, amount=Decimal(amount), method="cash",
                allocations=[{"student_fee_id": fee.id, "amount": Decimal(amount)}], recorded_by=None,
            )

    def _enable(self, school, **overrides):
        with tenant_context(school):
            NotificationSettings.objects.update_or_create(
                singleton=True, defaults={"fee_reminders_enabled": True, **overrides}
            )

    def _run(self, school, today):
        with tenant_context(school):
            return reminders.send_fee_reminders_for_current_school(today=today)

    def _alerts(self, school, kind=None):
        with tenant_context(school):
            qs = AlertLog.objects.all()
            if kind:
                qs = qs.filter(kind=kind)
            return list(qs.order_by("created_at"))

    def setUp(self):
        self.addCleanup(self._cleanup)
        self._cleanup()
        self.school = self._school(self.SCHEMA_A)
        self.student_user = self._user("student")
        self.parent_user = self._user("parent")
        self.student = self._student(self.school, "ENR-R-1", user=self.student_user)
        self._parent(self.school, self.student, self.parent_user)
        self.fee = self._fee(self.school, self.student)
        self._enable(self.school)


class SchoolSwitchAndRecipientTests(ReminderFixture):
    def test_a_school_that_never_enabled_reminders_sends_nothing(self):
        other = self._school(self.SCHEMA_B)
        student = self._student(other, "ENR-R-9", user=self._user("other_student"))
        self._fee(other, student)
        summary = self._run(other, DUE - timedelta(days=1))
        self.assertFalse(summary["enabled"])
        self.assertEqual(self._alerts(other), [])

    def test_a_disabled_school_stays_silent_even_when_fees_are_overdue(self):
        with tenant_context(self.school):
            NotificationSettings.objects.update(fee_reminders_enabled=False)
        self._run(self.school, DUE + timedelta(days=3))
        self.assertEqual(self._alerts(self.school), [])

    def test_the_student_and_the_linked_parent_both_receive_it(self):
        summary = self._run(self.school, DUE - timedelta(days=2))
        self.assertEqual(summary["sent"], 2)
        alerts = self._alerts(self.school, AlertLog.Kind.FEE_DUE_SOON)
        self.assertEqual({a.recipient_user_id for a in alerts}, {self.student_user.id, self.parent_user.id})
        with tenant_context(self.school):
            self.assertEqual(Notification.objects.count(), 2)
            self.assertEqual(EmailOutboxEvent.objects.count(), 2)

    def test_a_student_without_any_account_is_counted_not_alerted(self):
        lonely = self._student(self.school, "ENR-R-2")
        self._fee(self.school, lonely)
        summary = self._run(self.school, DUE - timedelta(days=1))
        self.assertEqual(summary["no_recipient"], 1)
        self.assertEqual(len(self._alerts(self.school)), 2)

    def test_a_recipient_without_an_email_still_gets_the_in_app_notice(self):
        quiet = self._user("quiet", email=False)
        student = self._student(self.school, "ENR-R-3", user=quiet)
        self._fee(self.school, student)
        self._run(self.school, DUE - timedelta(days=1))
        with tenant_context(self.school):
            self.assertTrue(Notification.objects.filter(recipient_user_id=quiet.id).exists())
            # Only the original student and parent have an address: no email for the quiet user.
            self.assertEqual(Notification.objects.count(), 3)
            self.assertEqual(EmailOutboxEvent.objects.count(), 2)

    def test_schools_are_independent(self):
        other = self._school(self.SCHEMA_B)
        student = self._student(other, "ENR-R-9", user=self._user("other_student"))
        self._fee(other, student)
        self._enable(other, fee_reminder_days_before=0)
        self._run(self.school, DUE - timedelta(days=1))
        self.assertEqual(len(self._alerts(other)), 0)
        self.assertEqual(len(self._alerts(self.school)), 2)


class DueSoonTests(ReminderFixture):
    def test_not_before_the_configured_number_of_days(self):
        self.assertEqual(self._run(self.school, DUE - timedelta(days=4))["sent"], 0)
        self.assertEqual(self._run(self.school, DUE - timedelta(days=3))["sent"], 2)

    def test_it_is_also_sent_on_the_due_date_itself(self):
        self.assertEqual(self._run(self.school, DUE)["sent"], 2)
        self.assertEqual(len(self._alerts(self.school, AlertLog.Kind.FEE_DUE_SOON)), 2)

    def test_it_is_sent_once_however_often_the_job_runs(self):
        for offset in (3, 3, 2, 1, 0):
            self._run(self.school, DUE - timedelta(days=offset))
        self.assertEqual(len(self._alerts(self.school, AlertLog.Kind.FEE_DUE_SOON)), 2)

    def test_a_missed_day_is_caught_up_on_the_next_run(self):
        self.assertEqual(self._run(self.school, DUE - timedelta(days=1))["sent"], 2)

    def test_zero_days_before_means_the_due_date_only(self):
        self._enable(self.school, fee_reminder_days_before=0)
        self.assertEqual(self._run(self.school, DUE - timedelta(days=1))["sent"], 0)
        self.assertEqual(self._run(self.school, DUE)["sent"], 2)

    def test_content_has_the_fee_the_balance_and_the_date_and_nothing_else(self):
        self._run(self.school, DUE - timedelta(days=1))
        with tenant_context(self.school):
            note = Notification.objects.first()
        self.assertEqual(note.title, "Fee due soon: Tuition")
        self.assertEqual(note.body, "Tuition: 1,500.00 outstanding, due on 2026-03-20.")
        self.assertEqual(note.category, "alert")
        for private in ("FirstENR-R-1", "Last", "ENR-R-1", "@rem.test"):
            self.assertNotIn(private, note.title + note.body)

    def test_the_amount_is_the_outstanding_balance_not_the_original(self):
        self._pay(self.school, self.fee, "400.00")
        self._run(self.school, DUE - timedelta(days=1))
        with tenant_context(self.school):
            self.assertIn("1,100.00 outstanding", Notification.objects.first().body)

    def test_a_changed_due_date_is_a_new_deadline(self):
        self._run(self.school, DUE - timedelta(days=1))
        with tenant_context(self.school):
            StudentFee.objects.filter(pk=self.fee.pk).update(due_date=DUE + timedelta(days=30))
        self._run(self.school, DUE + timedelta(days=29))
        self.assertEqual(len(self._alerts(self.school, AlertLog.Kind.FEE_DUE_SOON)), 4)


class OverdueTests(ReminderFixture):
    def sent_on(self, offset):
        return self._run(self.school, DUE + timedelta(days=offset))["sent"]

    def test_the_first_reminder_goes_out_the_day_after_the_due_date(self):
        self.assertEqual(self.sent_on(0), 2)  # due soon (due date itself)
        self.assertEqual(self.sent_on(1), 2)
        kinds = {a.kind for a in self._alerts(self.school)}
        self.assertEqual(kinds, {AlertLog.Kind.FEE_DUE_SOON, AlertLog.Kind.FEE_OVERDUE})

    def test_the_default_schedule_is_days_1_8_and_15_then_stops(self):
        results = {offset: self.sent_on(offset) for offset in (1, 2, 7, 8, 9, 14, 15, 16, 21, 22, 40)}
        self.assertEqual(
            {k: v for k, v in results.items() if v}, {1: 2, 8: 2, 15: 2}
        )
        self.assertEqual(len(self._alerts(self.school, AlertLog.Kind.FEE_OVERDUE)), 6)

    def test_a_missed_run_inside_a_window_is_caught_up(self):
        self.assertEqual(self.sent_on(5), 2)  # first run of the first window
        self.assertEqual(self.sent_on(6), 0)

    def test_a_missed_window_is_never_replayed(self):
        self.assertEqual(self.sent_on(8), 2)  # the first window (days 1-7) was missed entirely
        keys = {a.dedupe_key for a in self._alerts(self.school, AlertLog.Kind.FEE_OVERDUE)}
        self.assertTrue(all(key.endswith(":1") for key in keys))

    def test_a_fee_that_has_run_out_of_reminders_is_left_alone(self):
        self.assertEqual(self.sent_on(60), 0)
        self.assertEqual(self._alerts(self.school), [])

    def test_the_interval_and_the_maximum_are_configurable(self):
        self._enable(self.school, overdue_reminder_interval_days=2, max_overdue_reminders=2)
        results = {offset: self.sent_on(offset) for offset in range(1, 9)}
        self.assertEqual({k: v for k, v in results.items() if v}, {1: 2, 3: 2})

    def test_paying_in_full_stops_the_reminders(self):
        self.sent_on(1)
        self._pay(self.school, self.fee, "1500.00")
        self.assertEqual(self.sent_on(8), 0)

    def test_a_part_payment_keeps_them_going_with_the_new_balance(self):
        self._pay(self.school, self.fee, "500.00")
        self.sent_on(1)
        with tenant_context(self.school):
            self.assertEqual(Notification.objects.first().body, "Tuition: 1,000.00 outstanding, was due on 2026-03-20.")


class EligibilityTests(ReminderFixture):
    def test_nothing_is_sent_for_fees_that_do_not_qualify(self):
        cancelled = self._fee(self.school, self.student, due=DUE, amount="100.00",
                              head=self._head("Cancelled head"))
        with tenant_context(self.school):
            cancel_student_fee(StudentFee.objects.get(pk=cancelled.pk), reason="Entered in error")
        undated = self._fee(self.school, self.student, due=None, head=self._head("No date"))
        paid = self._fee(self.school, self.student, amount="50.00", head=self._head("Paid"))
        self._pay(self.school, paid, "50.00")
        with tenant_context(self.school):
            StudentFee.objects.filter(pk=self.fee.pk).delete()
        summary = self._run(self.school, DUE - timedelta(days=1))
        self.assertEqual(summary["sent"], 0)
        self.assertEqual(self._alerts(self.school), [])
        self.assertIsNotNone(undated)

    def _head(self, name):
        with tenant_context(self.school):
            return FeeHead.objects.get_or_create(name=name)[0]

    def test_a_student_who_is_no_longer_active_gets_nothing(self):
        for status in ("inactive", "graduated", "withdrawn", "transferred"):
            with self.subTest(status):
                with tenant_context(self.school):
                    Student.objects.filter(pk=self.student.pk).update(status=status)
                self.assertEqual(self._run(self.school, DUE - timedelta(days=1))["sent"], 0)

    def test_a_far_future_due_date_is_not_a_candidate(self):
        self.assertEqual(self._run(self.school, DUE - timedelta(days=60))["fees_considered"], 0)

    def test_several_fees_each_get_their_own_reminder(self):
        self._fee(self.school, self.student, due=DUE, amount="200.00", head=self._head("Transport"))
        summary = self._run(self.school, DUE - timedelta(days=1))
        self.assertEqual(summary["sent"], 4)
        with tenant_context(self.school):
            self.assertEqual(
                sorted(Notification.objects.filter(recipient_user_id=self.student_user.id).values_list("title", flat=True)),
                ["Fee due soon: Transport", "Fee due soon: Tuition"],
            )

    def test_the_public_schema_is_refused(self):
        connection.set_schema_to_public()
        with self.assertRaises(RuntimeError):
            reminders.send_fee_reminders_for_current_school(today=DUE)


class SchoolCalendarTests(TransactionTestCase):
    def test_today_follows_the_school_calendar_not_utc(self):
        cases = {
            datetime(2026, 3, 10, 18, 0, tzinfo=dt_timezone.utc): date(2026, 3, 10),  # 23:45 in Nepal
            datetime(2026, 3, 10, 18, 14, tzinfo=dt_timezone.utc): date(2026, 3, 10),  # 23:59
            datetime(2026, 3, 10, 18, 15, tzinfo=dt_timezone.utc): date(2026, 3, 11),  # 00:00
            datetime(2026, 3, 10, 19, 0, tzinfo=dt_timezone.utc): date(2026, 3, 11),  # 00:45
        }
        for moment, expected in cases.items():
            with self.subTest(moment=moment), mock.patch("fees.reminders.timezone.now", return_value=moment):
                self.assertEqual(reminders.alert_today(), expected)

    @override_settings(ALERT_TIME_ZONE="UTC")
    def test_the_zone_is_a_setting(self):
        moment = datetime(2026, 3, 10, 19, 0, tzinfo=dt_timezone.utc)
        with mock.patch("fees.reminders.timezone.now", return_value=moment):
            self.assertEqual(reminders.alert_today(), date(2026, 3, 10))

    def test_the_default_zone_is_kathmandu(self):
        self.assertEqual(settings.ALERT_TIME_ZONE, "Asia/Kathmandu")


class TaskTests(ReminderFixture):
    def test_the_task_covers_every_school_and_is_serialisable(self):
        other = self._school(self.SCHEMA_B)
        student = self._student(other, "ENR-R-9", user=self._user("other_student"))
        self._fee(other, student)
        self._enable(other)
        with mock.patch("fees.reminders.alert_today", return_value=DUE - timedelta(days=1)):
            summary = tasks.send_fee_reminders()
        json.dumps(summary)
        self.assertEqual(summary["schools_enabled"], 2)
        self.assertEqual(summary["sent"], 3)
        self.assertEqual(len(self._alerts(self.school)), 2)
        self.assertEqual(len(self._alerts(other)), 1)

    def test_running_the_task_twice_sends_nothing_new(self):
        with mock.patch("fees.reminders.alert_today", return_value=DUE - timedelta(days=1)):
            tasks.send_fee_reminders()
            summary = tasks.send_fee_reminders()
        self.assertEqual(summary["sent"], 0)
        self.assertEqual(summary["already_sent"], 2)

    def test_one_failing_school_does_not_stop_the_others(self):
        other = self._school(self.SCHEMA_B)
        student = self._student(other, "ENR-R-9", user=self._user("other_student"))
        self._fee(other, student)
        self._enable(other)
        real = reminders.send_fee_reminders_for_current_school

        def flaky(**kwargs):
            if connection.schema_name == self.SCHEMA_A:
                raise RuntimeError("boom")
            return real(**kwargs)

        with mock.patch("fees.reminders.alert_today", return_value=DUE - timedelta(days=1)), \
                mock.patch("fees.reminders.send_fee_reminders_for_current_school", side_effect=flaky), \
                self.assertLogs("fees.tasks", level="ERROR"):
            summary = tasks.send_fee_reminders()
        self.assertEqual(summary["errors"], 1)
        self.assertEqual(len(self._alerts(other)), 1)

    def test_an_exhausted_time_budget_defers_the_work(self):
        with mock.patch("fees.reminders.alert_today", return_value=DUE - timedelta(days=1)):
            summary = tasks.send_fee_reminders(time_budget=-1)
        self.assertEqual(summary["schools"], 0)
        self.assertEqual(summary["deferred"], 1)
        self.assertEqual(self._alerts(self.school), [])

    def test_a_deadline_inside_a_school_defers_the_remaining_fees(self):
        with tenant_context(self.school):
            summary = reminders.send_fee_reminders_for_current_school(
                today=DUE - timedelta(days=1), deadline=time.monotonic() - 1
            )
        self.assertEqual(summary["sent"], 0)
        self.assertEqual(summary["deferred"], 1)

    def test_it_is_scheduled_daily_and_has_its_own_time_limit(self):
        from config.celery import app
        from celery.schedules import crontab

        entry = settings.CELERY_BEAT_SCHEDULE["send-fee-reminders"]
        self.assertEqual(entry["task"], "fees.tasks.send_fee_reminders")
        self.assertEqual(entry["schedule"], crontab(hour=2, minute=30))
        self.assertIn(entry["task"], app.tasks)
        self.assertGreater(tasks.send_fee_reminders.time_limit, settings.CELERY_TASK_TIME_LIMIT)

    def test_a_failed_email_never_blocks_the_alert_record(self):
        with mock.patch("fees.reminders.alert_today", return_value=DUE - timedelta(days=1)), \
                mock.patch("notifications.services.queue_email", side_effect=RuntimeError("smtp")), \
                mock.patch("notifications.alerts.queue_email", side_effect=RuntimeError("smtp")), \
                self.assertLogs("fees.reminders", level="ERROR"):
            summary = tasks.send_fee_reminders()
        self.assertEqual(summary["errors"], 2)
        self.assertEqual(self._alerts(self.school), [])
