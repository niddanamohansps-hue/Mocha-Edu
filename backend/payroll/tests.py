"""Payroll Stage P1: salary structure (salaries, components, settings, the computed structure).

Creates tenant schemas and uses real threads for the race cases, so it needs a disposable
PostgreSQL database and is meant to be run only in an isolated test stage.
"""
import threading
import uuid
from datetime import date
from decimal import Decimal

from django.db import IntegrityError, connection, connections, transaction
from django.db.models.deletion import ProtectedError
from django.test import TransactionTestCase
from django_tenants.utils import schema_context, tenant_context
from rest_framework import serializers
from rest_framework.test import APIClient

from accounts.models import User
from core.models import AuditLog
from organizations.models import Domain, Organization
from profiles.models import Profile
from roles.constants import SYSTEM_PERMISSIONS
from roles.models import Permission, Role, UserRole
from staff.models import StaffMember

from . import services
from .models import PayrollSettings, SalaryComponent, StaffSalary, StaffSalaryComponent

D = Decimal
PASSWORD = "Pass1234!"
BASE = "/api/payroll"
Earning, Deduction = SalaryComponent.Kind.EARNING, SalaryComponent.Kind.DEDUCTION
Fixed, Percent = SalaryComponent.Calculation.FIXED, SalaryComponent.Calculation.PERCENT_OF_BASIC
JAN, MAR = date(2026, 1, 1), date(2026, 3, 1)


class PayrollFixture(TransactionTestCase):
    SCHEMA_A, DOMAIN_A = "pay_a", "pay-a.localhost"
    SCHEMA_B, DOMAIN_B = "pay_b", "pay-b.localhost"

    def _cleanup(self):
        connection.set_schema_to_public()
        for school in Organization.objects.filter(schema_name__in=[self.SCHEMA_A, self.SCHEMA_B]):
            school.delete(force_drop=True)
        User.objects.filter(username__startswith="pay_").delete()

    def _school(self, schema, domain):
        connection.set_schema_to_public()
        school = Organization.objects.create(schema_name=schema, name=schema)
        Domain.objects.create(domain=domain, tenant=school, is_primary=True)
        return school

    def _user(self, name, school, *, role_slug=None, codenames=None):
        connection.set_schema_to_public()
        user = User.objects.create_user(username=f"pay_{name}", email=f"pay_{name}@pay.test", password=PASSWORD)
        with tenant_context(school):
            Profile.objects.create(user_id=user.id, first_name=name, last_name="User")
            if role_slug:
                role = Role.objects.get(slug=role_slug)
            else:
                slug = f"pay-{uuid.uuid4().hex[:10]}"
                role = Role.objects.create(name=slug, slug=slug, is_system_role=False)
                role.permissions.set(Permission.objects.filter(codename__in=codenames or []))
            UserRole.objects.create(user=user, role=role)
        return user

    def _staff(self, school, employee_id, first="Sita", last="Karki", active=True):
        with tenant_context(school):
            profile = Profile.objects.create(first_name=first, last_name=last)
            return StaffMember.objects.create(profile=profile, employee_id=employee_id, designation="Teacher", is_active=active)

    def _call(self, user, method, path, data=None, host=None):
        client = APIClient()
        if user is not None:
            client.force_authenticate(user=user)
        return getattr(client, method)(f"{BASE}/{path}", data, format="json", HTTP_HOST=host or self.DOMAIN_A)

    def setUp(self):
        self.addCleanup(self._cleanup)
        self._cleanup()
        self.school = self._school(self.SCHEMA_A, self.DOMAIN_A)
        self.school_b = self._school(self.SCHEMA_B, self.DOMAIN_B)
        self.owner = self._user("owner", self.school, role_slug="owner")
        self.sita = self._staff(self.school, "E-P-1")
        self.ram = self._staff(self.school, "E-P-2", "Ram", "Thapa")
        with tenant_context(self.school):
            self.da = SalaryComponent.objects.create(name="Dearness allowance", code="DA", kind=Earning, calculation=Percent, default_value=D("10"))
            self.transport = SalaryComponent.objects.create(name="Transport", code="TRANSPORT", kind=Earning, calculation=Fixed, default_value=D("1500"))
            self.pf = SalaryComponent.objects.create(name="Provident fund", code="PF", kind=Deduction, calculation=Percent, default_value=D("10"))
            self.fine = SalaryComponent.objects.create(name="Staff welfare", code="WELFARE", kind=Deduction, calculation=Fixed, default_value=D("200"))

    def salary(self, staff=None, amount="30000", on=JAN, **kw):
        with tenant_context(self.school):
            return services.set_salary(staff=staff or self.sita, basic_amount=D(amount), effective_from=on, user_id=self.owner.id, **kw)

    def give(self, component, staff=None, on=JAN, value=None):
        with tenant_context(self.school):
            return services.assign_component(staff=staff or self.sita, component=component, effective_from=on,
                                             value=None if value is None else D(value), user_id=self.owner.id)

    def structure(self, staff=None, on=MAR):
        with tenant_context(self.school):
            return services.compute_structure(staff or self.sita, on)


class SalaryTests(PayrollFixture):
    def test_a_salary_is_recorded_and_a_raise_is_a_new_row(self):
        first = self.salary(amount="30000", on=JAN)
        second = self.salary(amount="33000", on=date(2026, 4, 1))
        with tenant_context(self.school):
            self.assertEqual(StaffSalary.objects.filter(staff=self.sita).count(), 2)
            self.assertEqual(services.salary_on(self.sita, date(2026, 3, 31)).pk, first.pk)
            self.assertEqual(services.salary_on(self.sita, date(2026, 4, 1)).pk, second.pk)
            self.assertIsNone(services.salary_on(self.sita, date(2025, 12, 31)))

    def test_bad_salaries_are_refused(self):
        for label, amount in {"zero": D("0"), "negative": D("-5"), "three decimals": D("100.001"), "absurd": D("99999999999.99"), "none": None}.items():
            with self.subTest(label):
                with tenant_context(self.school), self.assertRaises(serializers.ValidationError):
                    services.set_salary(staff=self.sita, basic_amount=amount, effective_from=JAN)
        with tenant_context(self.school):
            self.assertEqual(StaffSalary.objects.count(), 0)

    def test_a_second_salary_from_the_same_date_is_refused(self):
        self.salary(on=JAN)
        with tenant_context(self.school), self.assertRaises(serializers.ValidationError):
            services.set_salary(staff=self.sita, basic_amount=D("40000"), effective_from=JAN)

    def test_inactive_staff_cannot_be_given_a_salary(self):
        retired = self._staff(self.school, "E-P-9", "Old", "Timer", active=False)
        with tenant_context(self.school), self.assertRaises(serializers.ValidationError):
            services.set_salary(staff=retired, basic_amount=D("1000"), effective_from=JAN)

    def test_salary_records_are_immutable_and_protected(self):
        row = self.salary()
        with tenant_context(self.school):
            row = StaffSalary.objects.get(pk=row.pk)
            row.basic_amount = D("1")
            with self.assertRaises(RuntimeError):
                row.save()
            with self.assertRaises(RuntimeError):
                row.delete()
            with self.assertRaises(ProtectedError):
                self.sita.delete()
            with self.assertRaises(IntegrityError), transaction.atomic():
                StaffSalary.objects.filter(pk=row.pk).update(basic_amount=D("0"))

    def test_simultaneous_salary_changes_for_the_same_date_make_one_row(self):
        barrier = threading.Barrier(4)
        results, errors = [], []

        def run(index):
            try:
                with schema_context(self.SCHEMA_A):
                    barrier.wait(timeout=30)
                    services.set_salary(staff=self.sita, basic_amount=D(f"{20000 + index}"), effective_from=JAN)
                    results.append("ok")
            except serializers.ValidationError:
                results.append("refused")
            except Exception as exc:  # noqa: BLE001 - reported below
                errors.append(repr(exc))
            finally:
                connections.close_all()

        threads = [threading.Thread(target=run, args=(i,)) for i in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=90)
        self.assertEqual(errors, [])
        self.assertEqual((results.count("ok"), results.count("refused")), (1, 3))
        with tenant_context(self.school):
            self.assertEqual(StaffSalary.objects.filter(staff=self.sita).count(), 1)


class ComponentTests(PayrollFixture):
    def test_assigning_and_ending_a_component(self):
        assignment = self.give(self.transport)
        with tenant_context(self.school):
            services.end_component(assignment, effective_to=date(2026, 6, 30), user_id=self.owner.id)
            ended = StaffSalaryComponent.objects.get(pk=assignment.pk)
            self.assertEqual(ended.effective_to, date(2026, 6, 30))
            with self.assertRaises(serializers.ValidationError):
                services.end_component(ended, effective_to=date(2026, 7, 31))
            # once ended it can be given again
            services.assign_component(staff=self.sita, component=self.transport, effective_from=date(2026, 8, 1))
            self.assertEqual(StaffSalaryComponent.objects.filter(staff=self.sita, component=self.transport).count(), 2)

    def test_a_staff_member_cannot_hold_the_same_component_twice(self):
        self.give(self.transport)
        with tenant_context(self.school), self.assertRaises(serializers.ValidationError):
            services.assign_component(staff=self.sita, component=self.transport, effective_from=MAR)
        with tenant_context(self.school), self.assertRaises(IntegrityError), transaction.atomic():
            StaffSalaryComponent.objects.create(staff=self.sita, component=self.transport, effective_from=MAR)

    def test_an_end_date_before_the_start_is_refused(self):
        assignment = self.give(self.transport, on=MAR)
        with tenant_context(self.school), self.assertRaises(serializers.ValidationError):
            services.end_component(assignment, effective_to=JAN)

    def test_values_are_validated_by_calculation_type(self):
        cases = [
            (self.pf, D("100.001")), (self.pf, D("100.5")), (self.pf, D("-1")),   # a percentage: 0-100, 3 decimals
            (self.transport, D("10.005")), (self.transport, D("-3")), (self.transport, D("99999999999")),
        ]
        for component, value in cases:
            with self.subTest(component=component.code, value=value):
                with tenant_context(self.school), self.assertRaises(serializers.ValidationError):
                    services.assign_component(staff=self.sita, component=component, effective_from=JAN, value=value)
        self.give(self.pf, value="12.5")
        self.give(self.transport, value="2500.50")

    def test_inactive_components_and_inactive_staff_are_refused(self):
        with tenant_context(self.school):
            SalaryComponent.objects.filter(pk=self.fine.pk).update(is_active=False)
            self.fine.refresh_from_db()
            with self.assertRaises(serializers.ValidationError):
                services.assign_component(staff=self.sita, component=self.fine, effective_from=JAN)
        retired = self._staff(self.school, "E-P-8", "Old", "Timer", active=False)
        with tenant_context(self.school), self.assertRaises(serializers.ValidationError):
            services.assign_component(staff=retired, component=self.pf, effective_from=JAN)

    def test_components_in_use_are_protected_from_deletion(self):
        self.give(self.pf)
        with tenant_context(self.school):
            with self.assertRaises(ProtectedError):
                self.pf.delete()
            self.fine.delete()  # never used: can go

    def test_database_rules_on_components(self):
        with tenant_context(self.school):
            for bad in (dict(default_value=D("-1")), dict(calculation=Percent, default_value=D("100.5"))):
                with self.assertRaises(IntegrityError), transaction.atomic():
                    SalaryComponent.objects.filter(pk=self.fine.pk).update(**bad)

    def test_simultaneous_assignments_of_the_same_component_make_one(self):
        barrier = threading.Barrier(4)
        results, errors = [], []

        def run(_):
            try:
                with schema_context(self.SCHEMA_A):
                    barrier.wait(timeout=30)
                    services.assign_component(staff=self.sita, component=self.pf, effective_from=JAN)
                    results.append("ok")
            except serializers.ValidationError:
                results.append("refused")
            except Exception as exc:  # noqa: BLE001 - reported below
                errors.append(repr(exc))
            finally:
                connections.close_all()

        threads = [threading.Thread(target=run, args=(i,)) for i in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=90)
        self.assertEqual(errors, [])
        self.assertEqual((results.count("ok"), results.count("refused")), (1, 3))


class StructureTests(PayrollFixture):
    def test_the_structure_adds_up(self):
        self.salary(amount="30000")
        for component in (self.da, self.transport, self.pf, self.fine):
            self.give(component)
        result = self.structure()
        by_code = {l.code: l.amount for l in result.lines}
        self.assertEqual(by_code, {"BASIC": D("30000"), "DA": D("3000"), "TRANSPORT": D("1500"), "PF": D("3000"), "WELFARE": D("200")})
        self.assertEqual((result.gross, result.deductions, result.net), (D("34500"), D("3200"), D("31300")))
        self.assertFalse(result.net_is_negative)
        # the lines always add up exactly
        earnings = sum(l.amount for l in result.lines if l.kind in ("basic", "earning"))
        taken = sum(l.amount for l in result.lines if l.kind == "deduction")
        self.assertEqual((earnings, taken, earnings - taken), (result.gross, result.deductions, result.net))

    def test_a_per_person_value_overrides_the_default(self):
        self.salary(amount="30000")
        self.give(self.pf, value="12")
        self.give(self.transport, value="2000")
        amounts = {l.code: l.amount for l in self.structure().lines}
        self.assertEqual((amounts["PF"], amounts["TRANSPORT"]), (D("3600"), D("2000")))

    def test_changing_a_component_default_changes_people_without_an_override(self):
        self.salary(amount="30000")
        self.give(self.pf)
        with tenant_context(self.school):
            SalaryComponent.objects.filter(pk=self.pf.pk).update(default_value=D("11"))
        self.assertEqual({l.code: l.amount for l in self.structure().lines}["PF"], D("3300"))

    def test_rounding_to_the_whole_rupee_is_half_up_and_per_line(self):
        self.salary(amount="12345.50")
        self.give(self.pf, value="7.5")        # 12345.50 x 7.5% = 925.9125 -> 926
        self.give(self.da, value="10.1")       # 1246.9 (12345.5 * 10.1% = 1246.8955) -> 1247
        result = self.structure()
        amounts = {l.code: l.amount for l in result.lines}
        self.assertEqual(amounts["BASIC"], D("12346"))     # .50 rounds up
        self.assertEqual((amounts["PF"], amounts["DA"]), (D("926"), D("1247")))
        self.assertEqual(result.net, D("12346") + D("1247") - D("926"))
        self.assertTrue(all(l.amount == l.amount.to_integral_value() for l in result.lines))

    def test_keeping_paisa_when_the_school_turns_rounding_off(self):
        with tenant_context(self.school):
            PayrollSettings.update_singleton(round_to_whole_rupee=False)
        self.salary(amount="12345.50")
        self.give(self.pf, value="7.5")
        amounts = {l.code: l.amount for l in self.structure().lines}
        self.assertEqual((amounts["BASIC"], amounts["PF"]), (D("12345.50"), D("925.91")))   # 925.9125 -> 925.91

    def test_the_salary_and_components_in_force_on_a_date_are_used(self):
        self.salary(amount="30000", on=JAN)
        self.salary(amount="36000", on=date(2026, 4, 1))
        assignment = self.give(self.transport, on=date(2026, 2, 1))
        with tenant_context(self.school):
            services.end_component(assignment, effective_to=date(2026, 3, 31))
        before = {l.code: l.amount for l in self.structure(on=date(2026, 1, 15)).lines}
        in_march = {l.code: l.amount for l in self.structure(on=date(2026, 3, 31)).lines}
        in_april = {l.code: l.amount for l in self.structure(on=date(2026, 4, 1)).lines}
        self.assertEqual(set(before), {"BASIC"})                                   # transport not started
        self.assertEqual((in_march["BASIC"], in_march["TRANSPORT"]), (D("30000"), D("1500")))   # last day still counts
        self.assertEqual(in_april, {"BASIC": D("36000")})                           # raise applies, transport has ended

    def test_inactive_components_are_left_out_and_no_salary_means_no_structure(self):
        self.assertIsNone(self.structure())
        self.salary()
        self.give(self.transport)
        with tenant_context(self.school):
            SalaryComponent.objects.filter(pk=self.transport.pk).update(is_active=False)
        self.assertEqual({l.code for l in self.structure().lines}, {"BASIC"})

    def test_a_net_below_zero_is_reported_not_hidden(self):
        self.salary(amount="1000")
        self.give(self.fine, value="1500")
        result = self.structure()
        self.assertEqual(result.net, D("-500"))
        self.assertTrue(result.net_is_negative)

    def test_decimals_never_drift(self):
        self.salary(amount="0.10")
        with tenant_context(self.school):
            PayrollSettings.update_singleton(round_to_whole_rupee=False)
        self.give(self.da, value="0.001")
        self.assertEqual(self.structure().gross, D("0.10"))

    def test_other_staff_are_unaffected(self):
        self.salary(self.sita)
        self.give(self.pf, self.sita)
        self.assertIsNone(self.structure(self.ram))


class ApiTests(PayrollFixture):
    def setUp(self):
        super().setUp()
        self.viewer = self._user("viewer", self.school, codenames=["view_payroll"])
        self.manager = self._user("manager", self.school, codenames=["view_payroll", "manage_salary_structures"])
        self.staffer = self._user("staffer", self.school, role_slug="staff")
        self.teacher = self._user("teacher", self.school, role_slug="instructor")
        self.nobody = self._user("nobody", self.school, codenames=[])

    def test_the_new_permissions_exist_and_only_the_owner_holds_them(self):
        names = {"view_payroll", "manage_salary_structures"}
        self.assertTrue(names <= {p["codename"] for p in SYSTEM_PERMISSIONS})
        with tenant_context(self.school):
            self.assertTrue(names <= set(Role.objects.get(slug="owner").permissions.values_list("codename", flat=True)))
            for slug in ("staff", "instructor", "student", "parent"):
                self.assertFalse(names & set(Role.objects.get(slug=slug).permissions.values_list("codename", flat=True)), slug)

    def test_every_endpoint_needs_the_right_permission_and_staff_cannot_read_pay(self):
        self.salary()
        component = str(self.pf.id)
        cases = [
            ("get", "components/", None, self.viewer, self.nobody),
            ("get", "salaries/", None, self.viewer, self.nobody),
            ("get", f"salaries/history/?staff={self.sita.id}", None, self.viewer, self.nobody),
            ("get", f"salaries/structure/?staff={self.sita.id}", None, self.viewer, self.nobody),
            ("get", "staff-components/", None, self.viewer, self.nobody),
            ("get", "settings/", None, self.viewer, self.nobody),
            ("post", "components/", {"name": "N", "code": "n", "kind": "earning"}, self.manager, self.viewer),
            ("post", "salaries/", {"staff": str(self.ram.id), "basic_amount": "20000", "effective_from": "2026-01-01"}, self.manager, self.viewer),
            ("post", "staff-components/", {"staff": str(self.ram.id), "component": component, "effective_from": "2026-01-01"}, self.manager, self.viewer),
            ("patch", "settings/", {"round_to_whole_rupee": False}, self.manager, self.viewer),
        ]
        for method, path, data, allowed, denied in cases:
            with self.subTest(path=path, method=method):
                self.assertEqual(self._call(denied, method, path, data).status_code, 403)
                self.assertIn(self._call(None, method, path, data).status_code, (401, 403))
                self.assertIn(self._call(allowed, method, path, data).status_code, (200, 201))
        # ordinary staff and teachers see no pay at all (their own payslips come in a later stage)
        for person in (self.staffer, self.teacher):
            self.assertEqual(self._call(person, "get", "salaries/").status_code, 403)
            self.assertEqual(self._call(person, "get", f"salaries/structure/?staff={self.sita.id}").status_code, 403)

    def test_no_existing_staff_endpoint_reveals_salary(self):
        self.salary(amount="87654.32")
        for path in ("/api/staff/members/", f"/api/staff/members/{self.sita.id}/"):
            client = APIClient()
            client.force_authenticate(user=self.owner)
            body = client.get(path, HTTP_HOST=self.DOMAIN_A).content.decode()
            self.assertNotIn("87654", body, path)
            self.assertNotIn("salary", body.lower(), path)

    def test_setting_and_reading_salaries(self):
        from datetime import timedelta
        today = date.today()
        old, newer, future = (today - timedelta(days=400)).isoformat(), (today - timedelta(days=30)).isoformat(), (today + timedelta(days=3650)).isoformat()
        resp = self._call(self.owner, "post", "salaries/", {"staff": str(self.sita.id), "basic_amount": "30000.50", "effective_from": old, "note": "Joined"})
        self.assertEqual((resp.status_code, resp.data["basic_amount"], resp.data["employee_id"]), (201, "30000.50", "E-P-1"))
        self.assertEqual(self._call(self.owner, "post", "salaries/", {"staff": str(self.sita.id), "basic_amount": "35000", "effective_from": newer}).status_code, 201)
        self._call(self.owner, "post", "salaries/", {"staff": str(self.ram.id), "basic_amount": "25000", "effective_from": future})
        # only the salary in force today is listed: Sita's newer one; Ram's starts in the far future
        current = self._call(self.owner, "get", "salaries/").data["results"]
        self.assertEqual([(r["employee_id"], r["basic_amount"]) for r in current], [("E-P-1", "35000.00")])
        history = self._call(self.owner, "get", f"salaries/history/?staff={self.sita.id}").data["results"]
        self.assertEqual([r["basic_amount"] for r in history], ["35000.00", "30000.50"])
        self.assertEqual(self._call(self.owner, "get", "salaries/?search=sita").data["count"], 1)

    def test_bad_input_is_a_clean_400_or_404(self):
        base = {"staff": str(self.sita.id), "basic_amount": "30000", "effective_from": "2026-01-01"}
        for label, patch in {"zero": {"basic_amount": "0"}, "negative": {"basic_amount": "-1"}, "text": {"basic_amount": "abc"},
                             "three decimals": {"basic_amount": "10.123"}, "bad date": {"effective_from": "01-01-2026"},
                             "no staff": {"staff": None}, "unknown staff": {"staff": str(uuid.uuid4())}}.items():
            with self.subTest(label):
                self.assertEqual(self._call(self.owner, "post", "salaries/", {**base, **patch}).status_code, 400)
        self.assertEqual(self._call(self.owner, "post", "salaries/", []).status_code, 400)
        self.assertEqual(self._call(self.owner, "get", "salaries/history/").status_code, 400)
        self.assertEqual(self._call(self.owner, "get", "salaries/history/?staff=not-a-uuid").status_code, 400)
        self.assertEqual(self._call(self.owner, "get", f"salaries/history/?staff={uuid.uuid4()}").status_code, 404)
        self.assertEqual(self._call(self.owner, "get", f"salaries/structure/?staff={self.sita.id}&date=garbage").status_code, 400)
        self.assertEqual(self._call(self.owner, "get", f"salaries/structure/?staff={self.sita.id}").status_code, 404)  # no salary yet

    def test_salaries_cannot_be_edited_or_deleted_through_the_api(self):
        self.salary()
        with tenant_context(self.school):
            pk = StaffSalary.objects.first().pk
        for method in ("get", "put", "patch", "delete"):
            self.assertEqual(self._call(self.owner, method, f"salaries/{pk}/", {}).status_code, 404, method)  # no such route

    def test_components_end_to_end(self):
        resp = self._call(self.owner, "post", "components/", {"name": "Festival allowance", "code": "dashain", "kind": "earning", "calculation": "fixed", "default_value": "5000"})
        self.assertEqual((resp.status_code, resp.data["code"]), (201, "DASHAIN"))
        self.assertEqual(self._call(self.owner, "post", "components/", {"name": "Festival allowance", "code": "x", "kind": "earning"}).status_code, 400)
        self.assertEqual(self._call(self.owner, "post", "components/", {"name": "Other", "code": "DASHAIN", "kind": "earning"}).status_code, 400)
        self.assertEqual(self._call(self.owner, "post", "components/", {"name": "Bad pct", "code": "bp", "kind": "deduction", "calculation": "percent_of_basic", "default_value": "150"}).status_code, 400)
        self.assertEqual(self._call(self.owner, "post", "components/", {"name": "Neg", "code": "ng", "kind": "deduction", "default_value": "-1"}).status_code, 400)
        self.assertEqual(self._call(self.owner, "post", "components/", {"name": "Kind", "code": "kd", "kind": "bonus"}).status_code, 400)
        self.assertEqual(self._call(self.owner, "get", "components/?kind=deduction").data["count"], 2)
        self.assertEqual(self._call(self.owner, "get", "components/?search=pf").data["count"], 1)

    def test_a_component_in_use_cannot_change_type_or_be_deleted(self):
        self.give(self.pf)
        self.assertEqual(self._call(self.owner, "patch", f"components/{self.pf.id}/", {"kind": "earning"}).status_code, 400)
        self.assertEqual(self._call(self.owner, "patch", f"components/{self.pf.id}/", {"calculation": "fixed"}).status_code, 400)
        self.assertEqual(self._call(self.owner, "patch", f"components/{self.pf.id}/", {"default_value": "12", "is_active": True}).status_code, 200)
        self.assertEqual(self._call(self.owner, "delete", f"components/{self.pf.id}/").status_code, 409)
        self.assertEqual(self._call(self.owner, "delete", f"components/{self.fine.id}/").status_code, 204)

    def test_assigning_ending_and_the_structure_preview(self):
        self.salary(amount="30000")
        resp = self._call(self.owner, "post", "staff-components/", {"staff": str(self.sita.id), "component": str(self.pf.id), "effective_from": "2026-01-01", "value": "12"})
        self.assertEqual((resp.status_code, D(resp.data["effective_value"]), resp.data["kind"]), (201, D("12"), "deduction"))
        self.assertEqual(self._call(self.owner, "post", "staff-components/", {"staff": str(self.sita.id), "component": str(self.pf.id), "effective_from": "2026-02-01"}).status_code, 400)
        self.assertEqual(self._call(self.owner, "post", "staff-components/", {"staff": str(self.sita.id), "component": str(self.pf.id), "effective_from": "2026-01-01", "value": "150"}).status_code, 400)
        preview = self._call(self.owner, "get", f"salaries/structure/?staff={self.sita.id}&date=2026-03-01").data
        self.assertEqual((preview["basic"], preview["gross"], preview["deductions"], preview["net"]), ("30000", "30000", "3600", "26400"))
        self.assertEqual([l["code"] for l in preview["lines"]], ["BASIC", "PF"])
        end = self._call(self.owner, "post", f"staff-components/{resp.data['id']}/end/", {"effective_to": "2026-06-30"})
        self.assertEqual((end.status_code, end.data["effective_to"]), (200, "2026-06-30"))
        self.assertEqual(self._call(self.owner, "post", f"staff-components/{resp.data['id']}/end/", {"effective_to": "2026-07-31"}).status_code, 400)
        self.assertEqual(self._call(self.owner, "get", f"staff-components/?staff={self.sita.id}&open=true").data["count"], 0)

    def test_settings_default_and_update(self):
        resp = self._call(self.viewer, "get", "settings/")
        self.assertEqual((resp.data["round_to_whole_rupee"], resp.data["require_separate_approver"], resp.data["is_default"]), (True, True, True))
        with tenant_context(self.school):
            self.assertEqual(PayrollSettings.objects.count(), 0)  # reading never writes
        resp = self._call(self.owner, "patch", "settings/", {"round_to_whole_rupee": False})
        self.assertEqual((resp.status_code, resp.data["round_to_whole_rupee"], resp.data["is_default"]), (200, False, False))
        for bad in ({}, {"round_to_whole_rupee": "yes"}, {"unknown": True}):
            self.assertEqual(self._call(self.owner, "patch", "settings/", bad).status_code, 400, bad)
        for method in ("put", "post", "delete"):
            self.assertEqual(self._call(self.owner, method, "settings/", {}).status_code, 405, method)

    def test_every_change_is_audit_logged(self):
        self._call(self.owner, "post", "salaries/", {"staff": str(self.sita.id), "basic_amount": "30000", "effective_from": "2026-01-01"})
        self._call(self.owner, "post", "staff-components/", {"staff": str(self.sita.id), "component": str(self.pf.id), "effective_from": "2026-01-01"})
        self._call(self.owner, "patch", "settings/", {"require_separate_approver": False})
        with tenant_context(self.school):
            actions = set(AuditLog.objects.values_list("action", flat=True))
            self.assertTrue({"salary_set", "salary_component_assigned", "payroll_settings_changed"} <= actions)
            entry = AuditLog.objects.get(action="salary_set")
            self.assertEqual((entry.actor_id, entry.changes["basic_amount"]), (self.owner.id, "30000.00"))

    def test_schools_cannot_see_each_others_pay(self):
        self.salary()
        self.give(self.pf)
        user_b = self._user("owner_b", self.school_b, role_slug="owner")
        self.assertEqual(self._call(user_b, "get", "salaries/", host=self.DOMAIN_B).data["results"], [])
        self.assertEqual(self._call(user_b, "get", "components/", host=self.DOMAIN_B).data["results"], [])
        self.assertEqual(self._call(user_b, "get", f"salaries/history/?staff={self.sita.id}", host=self.DOMAIN_B).status_code, 404)
        self.assertEqual(self._call(user_b, "get", "salaries/", host=self.DOMAIN_A).status_code, 403)
