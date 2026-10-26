"""Fixes from the code review: the school-calendar day decides "today", and editing a copy cannot undo a loan.

Creates tenant schemas, so it needs a disposable PostgreSQL database.
"""
import threading
from datetime import date, datetime, timedelta, timezone as dt_timezone
from unittest import mock

from django.db import connections
from django.test import override_settings
from django_tenants.utils import tenant_context

from core.dates import school_today

from . import services
from .models import BookCopy, Loan
from .tests import LibraryFixture


@override_settings(ALERT_TIME_ZONE="Asia/Kolkata")
class SchoolDayTests(LibraryFixture):
    # 23 March 01:00 in India is still 22 March in UTC.
    EARLY_MORNING = datetime(2026, 3, 22, 19, 30, tzinfo=dt_timezone.utc)

    def test_a_book_can_be_issued_dated_today_just_after_midnight(self):
        copy, student = self.copy(), self.student("S1")
        with mock.patch("django.utils.timezone.now", return_value=self.EARLY_MORNING):
            loan = self.lend(copy, student=student, on=date(2026, 3, 23))
            default = self.lend(self.copy(self.book("Other"), "B"), student=self.student("S2"))
        self.assertEqual(loan.issued_on, date(2026, 3, 23))
        self.assertEqual(default.issued_on, date(2026, 3, 23), "an undated loan uses the school's day, not UTC's")
        self.assertEqual(default.due_on, date(2026, 4, 6))


class CopyEditTests(LibraryFixture):
    def test_editing_an_issued_copy_keeps_it_issued(self):
        copy = self.copy()
        self.lend(copy, student=self.student("S1"))
        resp = self._call(self.owner, "patch", f"copies/{copy.id}/", {"notes": "Spine taped"})
        self.assertEqual((resp.status_code, resp.data["status"], resp.data["notes"]), (200, "issued", "Spine taped"))

    def test_an_edit_racing_a_loan_cannot_mark_the_copy_available_again(self):
        copy, student = self.copy(), self.student("S1")
        outcomes = []

        def edit():
            try:
                outcomes.append(self._call(self.owner, "patch", f"copies/{copy.id}/", {"notes": "Checked"}).status_code)
            finally:
                connections.close_all()

        def lend():
            try:
                with tenant_context(self.school):
                    services.issue_book(copy=copy, student=student)
                outcomes.append("lent")
            finally:
                connections.close_all()

        threads = [threading.Thread(target=edit), threading.Thread(target=lend)]
        [t.start() for t in threads]
        [t.join() for t in threads]
        self.assertIn("lent", outcomes)
        with tenant_context(self.school):
            self.assertEqual(BookCopy.objects.get(pk=copy.pk).status, "issued")
            self.assertEqual(Loan.objects.filter(copy=copy, returned_on__isnull=True).count(), 1)
