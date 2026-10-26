"""Transport: vehicles, drivers, routes and stops, student seats (capacity, moves), the monthly billing run
into Fees, expiring documents and permissions.

Creates tenant schemas and uses real threads for the race cases, so it needs a disposable PostgreSQL
database and is meant to be run only in an isolated test stage.
"""
import threading
import uuid
from datetime import date, timedelta
from decimal import Decimal

from django.db import IntegrityError, connection, connections, transaction
from django.test import TransactionTestCase
from django.utils import timezone
from django_tenants.utils import tenant_context
from rest_framework import serializers
from rest_framework.test import APIClient

from academics.models import AcademicLevel, Program, Section
from accounts.models import User
from core.models import AuditLog
from fees.models import FeeHead, StudentFee
from organizations.models import Domain, Organization
from profiles.models import Profile
from roles.constants import SYSTEM_PERMISSIONS
from roles.models import Permission, Role, UserRole
from staff.models import StaffMember
from students.models import Student, StudentLevel

from . import services
from .models import Driver, Route, RouteStop, StudentTransport, TransportBill, Vehicle

D = Decimal
PASSWORD = "Pass1234!"
BASE = "/api/transport"
MARCH = date(2026, 3, 1)


class TransportFixture(TransactionTestCase):
    SCHEMA_A, DOMAIN_A = "trn_a", "trn-a.localhost"
    SCHEMA_B, DOMAIN_B = "trn_b", "trn-b.localhost"

    def _cleanup(self):
        connection.set_schema_to_public()
        for school in Organization.objects.filter(schema_name__in=[self.SCHEMA_A, self.SCHEMA_B]):
            school.delete(force_drop=True)
        User.objects.filter(username__startswith="trn_").delete()

    def _school(self, schema, domain):
        connection.set_schema_to_public()
        school = Organization.objects.create(schema_name=schema, name=schema)
        Domain.objects.create(domain=domain, tenant=school, is_primary=True)
        return school

    def _user(self, name, school, *, role_slug=None, codenames=None):
        connection.set_schema_to_public()
        user = User.objects.create_user(username=f"trn_{name}", email=f"trn_{name}@trn.test", password=PASSWORD)
        with tenant_context(school):
            Profile.objects.create(user_id=user.id, first_name=name, last_name="User")
            if role_slug:
                role = Role.objects.get(slug=role_slug)
            else:
                slug = f"trn-{uuid.uuid4().hex[:10]}"
                role = Role.objects.create(name=slug, slug=slug, is_system_role=False)
                role.permissions.set(Permission.objects.filter(codename__in=codenames or []))
            UserRole.objects.create(user=user, role=role)
        return user

    def _call(self, user, method, path, data=None, host=None):
        client = APIClient()
        if user is not None:
            client.force_authenticate(user=user)
        return getattr(client, method)(f"{BASE}/{path}", data, format="json", HTTP_HOST=host or self.DOMAIN_A)

    @staticmethod
    def rows(response):
        data = response.data
        return data["results"] if isinstance(data, dict) and "results" in data else data

    # --- builders (direct, in the school's schema) ---------------------------------------------------------
    def vehicle(self, reg="BA 1 KHA 1111", capacity=30, **kw):
        with tenant_context(self.school):
            return Vehicle.objects.create(registration_number=reg, capacity=capacity, **kw)

    def person(self, name="Hari Driver", role=Driver.Role.DRIVER, **kw):
        with tenant_context(self.school):
            return Driver.objects.create(full_name=name, role=role, **kw)

    def route(self, name="Route 1", vehicle=None, **kw):
        with tenant_context(self.school):
            return Route.objects.create(name=name, vehicle=vehicle, **kw)

    def stop(self, route, name="Stop A", sequence=1, fee="1500"):
        """``fee=None`` leaves the stop on the route's fee."""
        with tenant_context(self.school):
            return RouteStop.objects.create(route=route, name=name, sequence=sequence, monthly_fee=None if fee is None else D(fee))

    def student(self, enrollment, first="Kid", enrolled=True, status="active"):
        with tenant_context(self.school):
            student = Student.objects.create(
                profile=Profile.objects.create(first_name=first, last_name=enrollment),
                enrollment_id=enrollment, status=status,
            )
            if enrolled:
                StudentLevel.objects.create(
                    student=student, level=self.level, section=self.section, academic_year="2026", is_current=True
                )
            return student

    def seat(self, student, stop, start=date(2026, 2, 10), **kw):
        with tenant_context(self.school):
            return services.assign_student(student=student, route=stop.route, stop=stop, start_date=start, user_id=self.owner.id, **kw)

    def seat_on(self, student, route, start=date(2026, 2, 10), **kw):
        """A seat on a route that has no stops."""
        with tenant_context(self.school):
            return services.assign_student(student=student, route=route, start_date=start, user_id=self.owner.id, **kw)

    def bill(self, year=2026, month=3, **kw):
        with tenant_context(self.school):
            return services.bill_month(year=year, month=month, user_id=self.owner.id, **kw)

    def setUp(self):
        self.addCleanup(self._cleanup)
        self._cleanup()
        self.school = self._school(self.SCHEMA_A, self.DOMAIN_A)
        self.school_b = self._school(self.SCHEMA_B, self.DOMAIN_B)
        self.owner = self._user("owner", self.school, role_slug="owner")
        with tenant_context(self.school):
            program = Program.objects.create(name="School", code="SCH")
            self.level = AcademicLevel.objects.create(program=program, name="Grade 5", order=1)
            self.section = Section.objects.create(level=self.level, name="A", capacity=40)


class CrudTests(TransportFixture):
    def test_a_vehicle_is_created_with_an_upper_case_unique_number(self):
        resp = self._call(self.owner, "post", "vehicles/", {"registration_number": " ba 2 kha 2222 ", "capacity": 40})
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(resp.data["registration_number"], "BA 2 KHA 2222")
        again = self._call(self.owner, "post", "vehicles/", {"registration_number": "BA 2 KHA 2222", "capacity": 40})
        self.assertEqual(again.status_code, 400)

    def test_capacity_must_be_at_least_one(self):
        resp = self._call(self.owner, "post", "vehicles/", {"registration_number": "X1", "capacity": 0})
        self.assertEqual(resp.status_code, 400)
        self.assertIn("capacity", resp.data)

    def test_a_driver_may_be_linked_to_staff_or_stand_alone(self):
        with tenant_context(self.school):
            staff = StaffMember.objects.create(
                profile=Profile.objects.create(first_name="Sita", last_name="Karki"), employee_id="E-T-1", designation="Driver"
            )
        alone = self._call(self.owner, "post", "drivers/", {"full_name": "Contract Driver", "role": "driver", "license_expiry": "2027-01-01"})
        linked = self._call(self.owner, "post", "drivers/", {"full_name": "Sita Karki", "role": "driver", "staff": str(staff.id)})
        self.assertEqual((alone.status_code, linked.status_code), (201, 201))
        self.assertEqual(linked.data["staff_name"], "Sita Karki")
        self.assertEqual(alone.data["staff_name"], "")

    def test_a_route_needs_a_driver_in_the_driver_slot_and_a_helper_in_the_helper_slot(self):
        driver, helper = self.person("Drv"), self.person("Hlp", Driver.Role.HELPER)
        wrong = self._call(self.owner, "post", "routes/", {"name": "R", "driver": str(helper.id)})
        self.assertEqual(wrong.status_code, 400)
        wrong2 = self._call(self.owner, "post", "routes/", {"name": "R", "helper": str(driver.id)})
        self.assertEqual(wrong2.status_code, 400)
        ok = self._call(self.owner, "post", "routes/", {"name": "R", "driver": str(driver.id), "helper": str(helper.id)})
        self.assertEqual(ok.status_code, 201, ok.data)
        self.assertEqual((ok.data["driver_name"], ok.data["helper_name"]), ("Drv", "Hlp"))

    def test_stops_keep_unique_order_and_names_and_a_fee_not_below_zero(self):
        route = self.route()
        payload = {"route": str(route.id), "name": "Stop A", "sequence": 1, "monthly_fee": "1200.00"}
        self.assertEqual(self._call(self.owner, "post", "stops/", payload).status_code, 201)
        same_order = self._call(self.owner, "post", "stops/", {**payload, "name": "Stop B"})
        same_name = self._call(self.owner, "post", "stops/", {**payload, "sequence": 2})
        negative = self._call(self.owner, "post", "stops/", {**payload, "name": "C", "sequence": 3, "monthly_fee": "-1"})
        self.assertEqual([same_order.status_code, same_name.status_code, negative.status_code], [400, 400, 400])

    def test_a_stop_cannot_be_moved_to_another_route(self):
        r1, r2 = self.route("R1"), self.route("R2")
        stop = self.stop(r1)
        resp = self._call(self.owner, "patch", f"stops/{stop.id}/", {"route": str(r2.id)})
        self.assertEqual(resp.status_code, 400)

    def test_things_in_use_are_refused_with_409_and_unused_ones_delete(self):
        vehicle = self.vehicle(capacity=5)
        route = self.route(vehicle=vehicle)
        stop = self.stop(route)
        self.seat(self.student("S1"), stop)
        self.assertEqual(self._call(self.owner, "delete", f"vehicles/{vehicle.id}/").status_code, 409)
        self.assertEqual(self._call(self.owner, "delete", f"stops/{stop.id}/").status_code, 409)
        spare = self.vehicle("SPARE 1", 10)
        self.assertEqual(self._call(self.owner, "delete", f"vehicles/{spare.id}/").status_code, 204)

    def test_changes_are_audited(self):
        resp = self._call(self.owner, "post", "vehicles/", {"registration_number": "AUD 1", "capacity": 10})
        with tenant_context(self.school):
            self.assertTrue(AuditLog.objects.filter(action="vehicle_created", object_id=resp.data["id"]).exists())


class PermissionTests(TransportFixture):
    def setUp(self):
        super().setUp()
        self.viewer = self._user("viewer", self.school, codenames=["view_transport"])
        self.manager = self._user("manager", self.school, codenames=["view_transport", "manage_transport"])
        self.assigner = self._user("assigner", self.school, codenames=["view_transport", "assign_transport"])
        self.biller = self._user("biller", self.school, codenames=["view_transport", "bill_transport"])
        self.plain = self._user("plain", self.school, codenames=[])
        self.owner_b = self._user("owner_b", self.school_b, role_slug="owner")

    def test_the_four_permissions_exist_in_the_catalogue(self):
        codenames = {p["codename"] for p in SYSTEM_PERMISSIONS}
        self.assertTrue({"view_transport", "manage_transport", "assign_transport", "bill_transport"} <= codenames)

    def test_a_person_with_no_transport_permission_sees_nothing(self):
        for path in ("vehicles/", "drivers/", "routes/", "stops/", "seats/", "bills/", "expiring/"):
            self.assertEqual(self._call(self.plain, "get", path).status_code, 403, path)
        self.assertIn(self._call(None, "get", "vehicles/").status_code, (401, 403))

    def test_a_viewer_reads_but_cannot_change_anything(self):
        self.assertEqual(self._call(self.viewer, "get", "vehicles/").status_code, 200)
        self.assertEqual(self._call(self.viewer, "post", "vehicles/", {"registration_number": "V1", "capacity": 5}).status_code, 403)
        stop = self.stop(self.route(vehicle=self.vehicle()))
        student = self.student("S1")
        self.assertEqual(self._call(self.viewer, "post", "seats/", {"student": str(student.id), "route": str(stop.route_id), "stop": str(stop.id), "start_date": "2026-02-10"}).status_code, 403)
        self.assertEqual(self._call(self.viewer, "post", "bills/run/", {"month": "2026-03"}).status_code, 403)

    def test_each_permission_opens_only_its_own_action(self):
        vehicle = self.vehicle()
        stop = self.stop(self.route(vehicle=vehicle))
        student = self.student("S1")
        seat = {"student": str(student.id), "route": str(stop.route_id), "stop": str(stop.id), "start_date": "2026-02-10"}
        self.assertEqual(self._call(self.manager, "post", "vehicles/", {"registration_number": "M1", "capacity": 5}).status_code, 201)
        self.assertEqual(self._call(self.manager, "post", "seats/", seat).status_code, 403)
        self.assertEqual(self._call(self.assigner, "post", "vehicles/", {"registration_number": "A1", "capacity": 5}).status_code, 403)
        self.assertEqual(self._call(self.assigner, "post", "seats/", seat).status_code, 201)
        self.assertEqual(self._call(self.assigner, "post", "bills/run/", {"month": "2026-03"}).status_code, 403)
        self.assertEqual(self._call(self.biller, "post", "bills/run/", {"month": "2026-03"}).status_code, 200)

    def test_another_school_never_sees_this_schools_data(self):
        self.vehicle("MINE 1")
        mine = self._call(self.owner, "get", "vehicles/")
        theirs = self._call(self.owner_b, "get", "vehicles/", host=self.DOMAIN_B)
        self.assertEqual(len(self.rows(mine)), 1)
        self.assertEqual(self.rows(theirs), [])
        # a user of school B has no standing in school A at all
        self.assertEqual(self._call(self.owner_b, "get", "vehicles/").status_code, 403)


class SeatTests(TransportFixture):
    def setUp(self):
        super().setUp()
        self.bus = self.vehicle(capacity=2)
        self.r1 = self.route("R1", vehicle=self.bus)
        self.a, self.b = self.stop(self.r1, "A", 1), self.stop(self.r1, "B", 2, "2000")
        self.s1, self.s2, self.s3 = self.student("S1"), self.student("S2"), self.student("S3")

    def seats_of(self, student):
        with tenant_context(self.school):
            return list(StudentTransport.objects.filter(student=student).order_by("start_date"))

    def test_a_student_gets_a_seat_through_the_api(self):
        resp = self._call(self.owner, "post", "seats/", {"student": str(self.s1.id), "route": str(self.r1.id), "stop": str(self.a.id), "start_date": "2026-02-10"})
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual((resp.data["route_name"], resp.data["stop_name"], resp.data["is_open"], resp.data["mode"]), ("R1", "A", True, "both"))
        with tenant_context(self.school):
            self.assertTrue(AuditLog.objects.filter(action="transport_seat_assigned").exists())

    def test_moving_a_student_ends_the_old_seat_the_day_before_and_leaves_no_gap(self):
        self.seat(self.s1, self.a, date(2026, 2, 10))
        self.seat(self.s1, self.b, date(2026, 3, 5))
        first, second = self.seats_of(self.s1)
        self.assertEqual(first.end_date, date(2026, 3, 4))
        self.assertIsNone(second.end_date)

    def test_a_move_must_start_after_the_current_seat_began(self):
        self.seat(self.s1, self.a, date(2026, 2, 10))
        with self.assertRaises(serializers.ValidationError):
            self.seat(self.s1, self.b, date(2026, 2, 10))
        self.assertEqual(len(self.seats_of(self.s1)), 1)

    def test_using_the_same_stop_again_is_refused(self):
        self.seat(self.s1, self.a)
        with self.assertRaises(serializers.ValidationError):
            self.seat(self.s1, self.a, date(2026, 3, 1))

    def test_a_full_bus_takes_no_more_students(self):
        self.seat(self.s1, self.a)
        self.seat(self.s2, self.a)
        resp = self._call(self.owner, "post", "seats/", {"student": str(self.s3.id), "route": str(self.r1.id), "stop": str(self.b.id), "start_date": "2026-03-01"})
        self.assertEqual(resp.status_code, 400)
        self.assertIn("full", str(resp.data["route"]))

    def test_a_student_already_on_a_full_route_can_still_move_between_its_stops(self):
        self.seat(self.s1, self.a)
        self.seat(self.s2, self.a)
        self.seat(self.s1, self.b, date(2026, 3, 1))  # own seat does not count against them
        self.assertEqual(len([s for s in self.seats_of(self.s1) if s.end_date is None]), 1)

    def test_an_ended_seat_frees_the_place(self):
        seat = self.seat(self.s1, self.a)
        self.seat(self.s2, self.a)
        self.assertEqual(self._call(self.owner, "post", f"seats/{seat.id}/end/", {"end_date": "2026-03-01"}).status_code, 200)
        self.seat(self.s3, self.a, date(2026, 3, 2))

    def test_refused_cases(self):
        no_bus = self.stop(self.route("No bus"), "X", 1)
        off_route = self.route("Off", vehicle=self.vehicle("OFF 1", 5), is_active=False)
        off_stop = self.stop(off_route, "Y", 1)
        off_bus = self.route("Off bus", vehicle=self.vehicle("OFF 2", 5, is_active=False))
        off_bus_stop = self.stop(off_bus, "Z", 1)
        gone = self.student("GONE", status="withdrawn")
        for student, stop in ((self.s1, no_bus), (self.s1, off_stop), (self.s1, off_bus_stop), (gone, self.a)):
            with self.assertRaises(serializers.ValidationError):
                self.seat(student, stop)
        self.assertEqual(self.seats_of(self.s1), [])

    def test_ending_a_seat(self):
        seat = self.seat(self.s1, self.a, date(2026, 2, 10))
        early = self._call(self.owner, "post", f"seats/{seat.id}/end/", {"end_date": "2026-02-01"})
        self.assertEqual(early.status_code, 400)
        done = self._call(self.owner, "post", f"seats/{seat.id}/end/", {"end_date": "2026-03-20"})
        self.assertEqual((done.status_code, done.data["is_open"]), (200, False))
        again = self._call(self.owner, "post", f"seats/{seat.id}/end/", {"end_date": "2026-03-25"})
        self.assertEqual(again.status_code, 400)

    def test_seats_are_never_edited_or_deleted_through_the_api(self):
        seat = self.seat(self.s1, self.a)
        self.assertEqual(self._call(self.owner, "delete", f"seats/{seat.id}/").status_code, 405)
        self.assertEqual(self._call(self.owner, "patch", f"seats/{seat.id}/", {"end_date": "2026-03-01"}).status_code, 405)

    def test_the_database_allows_only_one_open_seat_per_student(self):
        self.seat(self.s1, self.a)
        with tenant_context(self.school):
            with self.assertRaises(IntegrityError):
                with transaction.atomic():
                    StudentTransport.objects.create(student=self.s1, route=self.r1, stop=self.b, start_date=date(2026, 3, 1))

    def test_a_seat_cannot_end_before_it_starts_in_the_database(self):
        with tenant_context(self.school):
            with self.assertRaises(IntegrityError):
                with transaction.atomic():
                    StudentTransport.objects.create(student=self.s1, route=self.r1, stop=self.a, start_date=date(2026, 3, 5), end_date=date(2026, 3, 1))

    def test_a_smaller_bus_or_lower_capacity_than_the_students_seated_is_refused(self):
        self.seat(self.s1, self.a)
        self.seat(self.s2, self.a)
        low = self._call(self.owner, "patch", f"vehicles/{self.bus.id}/", {"capacity": 1})
        self.assertEqual(low.status_code, 400)
        small = self.vehicle("SMALL 1", 1)
        swap = self._call(self.owner, "patch", f"routes/{self.r1.id}/", {"vehicle": str(small.id)})
        self.assertEqual(swap.status_code, 400)
        bigger = self._call(self.owner, "patch", f"vehicles/{self.bus.id}/", {"capacity": 40})
        self.assertEqual(bigger.status_code, 200)

    def test_a_route_with_students_cannot_be_switched_off_or_lose_its_bus(self):
        self.seat(self.s1, self.a)
        off = self._call(self.owner, "patch", f"routes/{self.r1.id}/", {"is_active": False})
        no_bus = self._call(self.owner, "patch", f"routes/{self.r1.id}/", {"vehicle": None})
        self.assertEqual((off.status_code, no_bus.status_code), (400, 400))

    def test_the_route_roster_lists_current_students_in_stop_order(self):
        self.seat(self.s2, self.b)
        self.seat(self.s1, self.a)
        resp = self._call(self.owner, "get", f"routes/{self.r1.id}/students/")
        self.assertEqual([r["stop_name"] for r in resp.data], ["A", "B"])
        route = self._call(self.owner, "get", f"routes/{self.r1.id}/")
        self.assertEqual((route.data["seats_taken"], route.data["capacity"]), (2, 2))

    def test_two_people_taking_the_last_seat_at_once_cannot_both_succeed(self):
        self.seat(self.s1, self.a)
        outcomes = []

        def take(student):
            try:
                with tenant_context(self.school):
                    services.assign_student(student=student, route=self.r1, stop=self.b, start_date=date(2026, 3, 1))
                outcomes.append("ok")
            except serializers.ValidationError:
                outcomes.append("full")
            finally:
                connections.close_all()

        threads = [threading.Thread(target=take, args=(s,)) for s in (self.s2, self.s3)]
        [t.start() for t in threads]
        [t.join() for t in threads]
        self.assertEqual(sorted(outcomes), ["full", "ok"])
        with tenant_context(self.school):
            self.assertEqual(StudentTransport.objects.filter(stop__route=self.r1, end_date__isnull=True).count(), 2)


class BillingTests(TransportFixture):
    def setUp(self):
        super().setUp()
        self.r1 = self.route("R1", vehicle=self.vehicle(capacity=50))
        self.a, self.b = self.stop(self.r1, "A", 1, "1500"), self.stop(self.r1, "B", 2, "2200.50")
        self.s1, self.s2 = self.student("S1"), self.student("S2")

    def fees(self, student=None):
        with tenant_context(self.school):
            qs = StudentFee.objects.filter(fee_head__name="Transport")
            return list(qs.filter(student=student) if student else qs)

    def test_a_run_adds_one_transport_fee_per_seated_student(self):
        self.seat(self.s1, self.a)
        self.seat(self.s2, self.b)
        summary = self.bill()
        self.assertEqual((summary["billed"], summary["total"]), (2, "3700.50"))
        fee = self.fees(self.s1)[0]
        self.assertEqual((fee.amount_due, fee.due_date, fee.academic_year, fee.status), (D("1500.00"), date(2026, 3, 31), "2026", "active"))
        with tenant_context(self.school):
            bill = TransportBill.objects.get(student=self.s2)
            self.assertEqual((bill.month, bill.amount, bill.student_fee.amount_due), (MARCH, D("2200.50"), D("2200.50")))

    def test_repeating_the_run_never_bills_twice(self):
        self.seat(self.s1, self.a)
        self.bill()
        again = self.bill()
        self.assertEqual((again["billed"], again["already_billed"]), (0, 1))
        self.assertEqual(len(self.fees()), 1)

    def test_a_student_added_after_the_first_run_is_billed_by_the_next(self):
        self.seat(self.s1, self.a)
        self.bill()
        self.seat(self.s2, self.a, date(2026, 3, 15))
        second = self.bill()
        self.assertEqual((second["billed"], second["already_billed"]), (1, 1))

    def test_only_seats_that_cover_a_day_of_the_month_are_billed(self):
        self.seat(self.s1, self.a, date(2026, 4, 1))  # starts after March
        seat = self.seat(self.s2, self.a, date(2026, 1, 5))
        with tenant_context(self.school):
            services.end_assignment(assignment=seat, end_date=date(2026, 2, 28))  # ended before March
        self.assertEqual(self.bill()["billed"], 0)
        edge = self.student("EDGE")
        edge_seat = self.seat(edge, self.a, date(2026, 1, 5))
        with tenant_context(self.school):
            services.end_assignment(assignment=edge_seat, end_date=date(2026, 3, 1))  # last day is the 1st: still billed
        self.assertEqual(self.bill()["billed"], 1)

    def test_a_student_who_moved_during_the_month_is_billed_for_the_new_stop(self):
        self.seat(self.s1, self.a, date(2026, 2, 10))
        self.seat(self.s1, self.b, date(2026, 3, 12))
        self.bill()
        self.assertEqual([f.amount_due for f in self.fees(self.s1)], [D("2200.50")])

    def test_free_stops_inactive_students_and_students_without_enrolment(self):
        free = self.stop(self.r1, "Free", 3, "0")
        gone = self.student("GONE")
        lone = self.student("LONE", first="Lonely", enrolled=False)
        self.seat(self.s1, free)
        self.seat(gone, self.a)
        self.seat(lone, self.a)
        with tenant_context(self.school):
            Student.objects.filter(pk=gone.pk).update(status="withdrawn")
        summary = self.bill()
        self.assertEqual((summary["billed"], summary["no_fee"]), (0, 1))
        self.assertEqual(summary["no_enrollment"], ["Lonely LONE"])
        self.assertEqual(self.fees(), [])

    def test_a_month_that_has_not_started_cannot_be_billed(self):
        future = timezone.localdate() + timedelta(days=62)
        resp = self._call(self.owner, "post", "bills/run/", {"month": f"{future.year}-{future.month:02d}"})
        self.assertEqual(resp.status_code, 400)

    def test_bad_input_is_refused(self):
        for payload in ({"month": "March"}, {"month": "2026-13"}, {"month": "1999-03"}, {"month": "2026-03", "due_date": "2026-02-01"}, {}):
            self.assertEqual(self._call(self.owner, "post", "bills/run/", payload).status_code, 400, payload)

    def test_a_chosen_due_date_is_used(self):
        self.seat(self.s1, self.a)
        self._call(self.owner, "post", "bills/run/", {"month": "2026-03", "due_date": "2026-03-10"})
        self.assertEqual(self.fees(self.s1)[0].due_date, date(2026, 3, 10))

    def test_a_switched_off_transport_fee_head_stops_the_run(self):
        self.seat(self.s1, self.a)
        with tenant_context(self.school):
            FeeHead.objects.update_or_create(name="Transport", defaults={"is_active": False})
        self.assertEqual(self._call(self.owner, "post", "bills/run/", {"month": "2026-03"}).status_code, 400)
        self.assertEqual(self.fees(), [])

    def test_the_bill_list_filters_by_month_and_the_run_is_audited(self):
        self.seat(self.s1, self.a, date(2026, 1, 5))
        self._call(self.owner, "post", "bills/run/", {"month": "2026-02"})
        self._call(self.owner, "post", "bills/run/", {"month": "2026-03"})
        march = self._call(self.owner, "get", "bills/?month=2026-03")
        self.assertEqual([r["month"] for r in self.rows(march)], ["2026-03-01"])
        self.assertEqual(len(self.rows(self._call(self.owner, "get", "bills/"))), 2)
        self.assertEqual(self._call(self.owner, "get", "bills/?month=bad").status_code, 400)
        with tenant_context(self.school):
            self.assertEqual(AuditLog.objects.filter(action="transport_billed").count(), 2)

    def test_a_bill_cannot_exist_twice_for_one_student_and_month_in_the_database(self):
        self.seat(self.s1, self.a)
        self.bill()
        with tenant_context(self.school):
            first = TransportBill.objects.get()
            extra = StudentFee.objects.create(student=self.s1, fee_head=first.student_fee.fee_head, academic_year="2026", amount_due=D("1"))
            with self.assertRaises(IntegrityError):
                with transaction.atomic():
                    TransportBill.objects.create(student=self.s1, month=MARCH, route=self.r1, stop=self.a, amount=D("1"), student_fee=extra)

    def test_two_runs_at_the_same_moment_still_bill_each_student_once(self):
        self.seat(self.s1, self.a)
        self.seat(self.s2, self.b)
        billed = []

        def run():
            try:
                with tenant_context(self.school):
                    billed.append(services.bill_month(year=2026, month=3)["billed"])
            finally:
                connections.close_all()

        threads = [threading.Thread(target=run) for _ in range(2)]
        [t.start() for t in threads]
        [t.join() for t in threads]
        self.assertEqual(sum(billed), 2)
        self.assertEqual(len(self.fees()), 2)
        with tenant_context(self.school):
            self.assertEqual(TransportBill.objects.count(), 2)


class ExpiringDocumentsTests(TransportFixture):
    TODAY = date(2026, 6, 1)

    def test_only_dates_that_are_past_or_close_are_listed_soonest_first(self):
        self.vehicle("SOON 1", insurance_expiry=date(2026, 6, 20), fitness_expiry=date(2027, 1, 1))
        self.vehicle("PAST 1", fitness_expiry=date(2026, 5, 1))
        self.vehicle("OFF 1", insurance_expiry=date(2026, 6, 2), is_active=False)
        self.person("Late Driver", license_expiry=date(2026, 6, 30))
        self.person("Far Driver", license_expiry=date(2028, 1, 1))
        with tenant_context(self.school):
            rows = services.expiring_documents(days=30, today=self.TODAY)
        self.assertEqual(
            [(r["subject"], r["document"], r["days_left"]) for r in rows],
            [("PAST 1", "Fitness certificate", -31), ("SOON 1", "Insurance", 19), ("Late Driver", "Licence", 29)],
        )

    def test_the_api_validates_the_window(self):
        for days in ("abc", "-1", "400"):
            self.assertEqual(self._call(self.owner, "get", f"expiring/?days={days}").status_code, 400, days)
        self.assertEqual(self._call(self.owner, "get", "expiring/?days=30").status_code, 200)


class StopsAreOptionalTests(TransportFixture):
    """Some schools have stops and some do not; the route's fee is the default and a stop's fee overrides it."""

    def setUp(self):
        super().setUp()
        self.bus = self.vehicle(capacity=10)
        self.flat = self.route("Flat fare", vehicle=self.bus, monthly_fee=D("1800"))
        self.s1, self.s2 = self.student("S1"), self.student("S2")

    def fee_of(self, student):
        with tenant_context(self.school):
            return StudentFee.objects.get(student=student, fee_head__name="Transport").amount_due

    def assign(self, student, route, stop):
        with tenant_context(self.school):
            return services.assign_student(student=student, route=route, stop=stop, start_date=date(2026, 2, 10))

    def test_a_route_without_stops_takes_a_seat_directly_and_bills_the_route_fee(self):
        resp = self._call(self.owner, "post", "seats/", {
            "student": str(self.s1.id), "route": str(self.flat.id), "start_date": "2026-02-10", "pickup_note": "near the temple",
        })
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(
            (resp.data["stop"], resp.data["stop_name"], resp.data["monthly_fee"], resp.data["pickup_note"]),
            (None, "", "1800.00", "near the temple"),
        )
        self.assertEqual(self.bill()["billed"], 1)
        self.assertEqual(self.fee_of(self.s1), D("1800.00"))
        with tenant_context(self.school):
            bill = TransportBill.objects.get()
            self.assertEqual((bill.route_id, bill.stop_id, bill.amount), (self.flat.id, None, D("1800.00")))
        listed = self.rows(self._call(self.owner, "get", "bills/?month=2026-03"))
        self.assertEqual((listed[0]["route_name"], listed[0]["stop_name"]), ("Flat fare", ""))

    def test_a_route_without_stops_refuses_a_stop_from_elsewhere(self):
        other = self.stop(self.route("Has stops", vehicle=self.vehicle("B2", 5)), "X", 1)
        with self.assertRaises(serializers.ValidationError):
            self.assign(self.s1, self.flat, other)

    def test_a_route_with_stops_needs_one(self):
        with_stops = self.route("With stops", vehicle=self.vehicle("B3", 5), monthly_fee=D("1000"))
        self.stop(with_stops, "A", 1, None)
        resp = self._call(self.owner, "post", "seats/", {"student": str(self.s1.id), "route": str(with_stops.id), "start_date": "2026-02-10"})
        self.assertEqual(resp.status_code, 400)
        self.assertIn("stop", resp.data)

    def test_a_stop_from_another_route_is_refused(self):
        mine = self.route("Mine", vehicle=self.vehicle("B4", 5))
        self.stop(mine, "Own", 1)
        theirs = self.stop(self.route("Theirs", vehicle=self.vehicle("B5", 5)), "Alien", 1)
        with self.assertRaises(serializers.ValidationError):
            self.assign(self.s1, mine, theirs)

    def test_a_stop_without_its_own_fee_uses_the_route_fee(self):
        route = self.route("Fallback", vehicle=self.vehicle("B6", 5), monthly_fee=D("1200"))
        plain = self.stop(route, "Plain", 1, None)
        self.seat(self.s1, plain)
        self.bill()
        self.assertEqual(self.fee_of(self.s1), D("1200.00"))

    def test_a_stop_fee_overrides_the_route_fee_even_when_zero(self):
        route = self.route("Override", vehicle=self.vehicle("B7", 5), monthly_fee=D("1200"))
        far = self.stop(route, "Far", 1, "2500")
        free = self.stop(route, "Free", 2, "0")
        self.seat(self.s1, far)
        self.seat(self.s2, free)
        summary = self.bill()
        self.assertEqual((summary["billed"], summary["no_fee"]), (1, 1))
        self.assertEqual(self.fee_of(self.s1), D("2500.00"))

    def test_a_route_with_no_fee_at_all_bills_nobody(self):
        free = self.route("Free route", vehicle=self.vehicle("B8", 5))
        self.seat_on(self.s1, free)
        summary = self.bill()
        self.assertEqual((summary["billed"], summary["no_fee"]), (0, 1))

    def test_the_effective_fee_is_shown_on_stops_and_seats(self):
        route = self.route("Shown", vehicle=self.vehicle("B9", 5), monthly_fee=D("900"))
        inherit = self.stop(route, "Inherit", 1, None)
        resp = self._call(self.owner, "get", f"stops/?route={route.id}")
        row = resp.data[0]
        self.assertEqual((row["monthly_fee"], row["fee"]), (None, "900.00"))
        self.assertEqual(self.seat(self.s1, inherit).fee, D("900"))

    def test_fees_must_not_be_negative(self):
        bad_route = self._call(self.owner, "post", "routes/", {"name": "Neg", "monthly_fee": "-5"})
        self.assertEqual(bad_route.status_code, 400)
        route = self.route("Ok")
        bad_stop = self._call(self.owner, "post", "stops/", {"route": str(route.id), "name": "S", "sequence": 1, "monthly_fee": "-1"})
        self.assertEqual(bad_stop.status_code, 400)
        with tenant_context(self.school):
            with self.assertRaises(IntegrityError):
                with transaction.atomic():
                    Route.objects.create(name="DB neg", monthly_fee=D("-1"))

    def test_start_and_end_points_are_stored(self):
        resp = self._call(self.owner, "post", "routes/", {"name": "Labelled", "start_point": "Koteshwor", "end_point": "School", "monthly_fee": "1500"})
        self.assertEqual(
            (resp.status_code, resp.data["start_point"], resp.data["end_point"], resp.data["monthly_fee"]),
            (201, "Koteshwor", "School", "1500.00"),
        )


class SeatModeTests(TransportFixture):
    def setUp(self):
        super().setUp()
        self.route1 = self.route("R1", vehicle=self.vehicle(capacity=5), monthly_fee=D("1000"))
        self.s1 = self.student("S1")

    def test_a_seat_is_both_ways_unless_said_otherwise(self):
        self.assertEqual(self.seat_on(self.s1, self.route1).mode, "both")
        other = self.student("S2")
        self.assertEqual(self.seat_on(other, self.route1, mode="pickup").mode, "pickup")

    def test_a_bad_mode_is_refused(self):
        resp = self._call(self.owner, "post", "seats/", {
            "student": str(self.s1.id), "route": str(self.route1.id), "start_date": "2026-02-10", "mode": "sideways",
        })
        self.assertEqual(resp.status_code, 400)

    def test_changing_the_mode_is_a_move_that_keeps_history(self):
        self.seat_on(self.s1, self.route1, date(2026, 2, 10))
        self.seat_on(self.s1, self.route1, date(2026, 3, 1), mode="dropoff")
        with tenant_context(self.school):
            first, second = StudentTransport.objects.filter(student=self.s1).order_by("start_date")
        self.assertEqual((first.mode, first.end_date, second.mode, second.end_date), ("both", date(2026, 2, 28), "dropoff", None))

    def test_the_identical_seat_again_is_refused(self):
        self.seat_on(self.s1, self.route1)
        with self.assertRaises(serializers.ValidationError):
            self.seat_on(self.s1, self.route1, date(2026, 3, 1))

    def test_the_seat_list_filters_by_route_and_mode(self):
        other_route = self.route("R2", vehicle=self.vehicle("MODE 2", 5))
        s2 = self.student("S2")
        self.seat_on(self.s1, self.route1, mode="pickup")
        self.seat_on(s2, other_route)
        by_route = self._call(self.owner, "get", f"seats/?route={self.route1.id}")
        by_mode = self._call(self.owner, "get", "seats/?mode=pickup")
        self.assertEqual([r["enrollment_id"] for r in self.rows(by_route)], ["S1"])
        self.assertEqual([r["enrollment_id"] for r in self.rows(by_mode)], ["S1"])
