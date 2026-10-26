"""Fixes from the code review: capacity counts seats by date, a cancelled transport fee can be billed again,
and the school-calendar day decides what "today" is.

Creates tenant schemas, so it needs a disposable PostgreSQL database.
"""
from datetime import date, datetime, timedelta, timezone as dt_timezone
from decimal import Decimal
from unittest import mock

from django.test import override_settings
from django_tenants.utils import tenant_context
from rest_framework import serializers

from core.dates import school_today
from fees.models import StudentFee
from fees.services import cancel_student_fee

from . import services
from .models import StudentTransport, TransportBill
from .tests import TransportFixture

D = Decimal


class CapacityByDateTests(TransportFixture):
    def setUp(self):
        super().setUp()
        self.today = school_today()
        self.bus = self.vehicle(capacity=2)
        self.r1 = self.route("R1", vehicle=self.bus, monthly_fee=D("1000"))
        self.r2 = self.route("R2", vehicle=self.vehicle("BIG 1", 40), monthly_fee=D("1000"))
        self.s1, self.s2, self.s3 = self.student("S1"), self.student("S2"), self.student("S3")

    def test_a_seat_ending_later_still_counts_until_it_ends(self):
        start = self.today - timedelta(days=10)
        self.seat_on(self.s1, self.r1, start)
        self.seat_on(self.s2, self.r1, start)
        # S1 moves to another route from next month: their seat on R1 runs until then.
        self.seat_on(self.s1, self.r2, self.today + timedelta(days=30))
        with self.assertRaises(serializers.ValidationError):
            self.seat_on(self.s3, self.r1, self.today)
        # From the day S1 has left, there is room.
        self.seat_on(self.s3, self.r1, self.today + timedelta(days=30))

    def test_a_seat_starting_later_blocks_an_open_seat_that_would_overlap_it(self):
        self.seat_on(self.s1, self.r1, self.today)
        self.seat_on(self.s2, self.r1, self.today + timedelta(days=20))
        with self.assertRaises(serializers.ValidationError):
            self.seat_on(self.s3, self.r1, self.today + timedelta(days=5))

    def test_a_seat_that_has_ended_frees_the_place(self):
        seat = self.seat_on(self.s1, self.r1, self.today - timedelta(days=40))
        self.seat_on(self.s2, self.r1, self.today - timedelta(days=40))
        with tenant_context(self.school):
            services.end_assignment(assignment=seat, end_date=self.today - timedelta(days=1))
        self.seat_on(self.s3, self.r1, self.today)

    def test_the_route_shows_the_peak_from_today(self):
        self.seat_on(self.s1, self.r1, self.today)
        self.seat_on(self.s2, self.r1, self.today + timedelta(days=15))
        with tenant_context(self.school):
            self.assertEqual(services.seats_taken(self.r1), 2)
            self.assertEqual(services.seats_taken(self.r1, on=self.today + timedelta(days=15)), 2)


class RebillAfterCancelTests(TransportFixture):
    def setUp(self):
        super().setUp()
        self.r1 = self.route("R1", vehicle=self.vehicle(capacity=10), monthly_fee=D("1500"))
        self.s1 = self.student("S1")
        self.seat_on(self.s1, self.r1, date(2026, 2, 10))

    def test_a_cancelled_transport_fee_can_be_billed_again(self):
        self.bill()
        with tenant_context(self.school):
            first = StudentFee.objects.get(fee_head__name="Transport")
            cancel_student_fee(first, reason="Billed the wrong amount")
        again = self.bill()
        self.assertEqual(again["billed"], 1)
        with tenant_context(self.school):
            fees = StudentFee.objects.filter(fee_head__name="Transport").order_by("created_at")
            self.assertEqual([f.status for f in fees], ["cancelled", "active"])
            bill = TransportBill.objects.get()
            self.assertEqual(bill.student_fee_id, fees.last().id)

    def test_an_active_fee_is_still_never_billed_twice(self):
        self.bill()
        self.assertEqual(self.bill()["already_billed"], 1)
        with tenant_context(self.school):
            self.assertEqual(StudentFee.objects.filter(fee_head__name="Transport").count(), 1)


@override_settings(ALERT_TIME_ZONE="Asia/Kolkata")
class SchoolDayTests(TransportFixture):
    def test_the_first_of_the_month_can_be_billed_before_utc_catches_up(self):
        # 1 March 01:00 in India is still 28 February in UTC.
        moment = datetime(2026, 2, 28, 19, 30, tzinfo=dt_timezone.utc)
        with mock.patch("django.utils.timezone.now", return_value=moment):
            self.assertEqual(school_today(), date(2026, 3, 1))
            summary = self.bill(year=2026, month=3)
        self.assertEqual(summary["month"], "2026-03-01")
