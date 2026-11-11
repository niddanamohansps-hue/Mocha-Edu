import datetime
from decimal import Decimal
from types import SimpleNamespace

from django.test import SimpleTestCase, TransactionTestCase
from django_tenants.utils import tenant_context

from . import charging
from .models import ConcessionType, FeeStructure, StudentConcession, StudentFee
from .services import get_outstanding_balance
from .tests import FeesFixtureMixin

D = Decimal


class SplitTests(SimpleTestCase):
    def test_parts_always_add_up_to_the_amount(self):
        for amount, percents in [
            (D("1000"), [D("33.33"), D("33.33"), D("33.34")]),
            (D("36000"), [D("40"), D("30"), D("30")]),
            (D("999.99"), [D("50"), D("50")]),
            (D("100"), [D("100")]),
        ]:
            parts = charging.split(amount, percents)
            self.assertEqual(sum(parts), amount)
            self.assertEqual(len(parts), len(percents))

    def test_rounding_remainder_goes_on_the_last_part(self):
        self.assertEqual(charging.split(D("100"), [D("33.33"), D("33.33"), D("33.34")]), [D("33.33"), D("33.33"), D("33.34")])
        self.assertEqual(charging.split(D("10"), [D("33.33"), D("66.67")]), [D("3.33"), D("6.67")])

    def test_plan_must_add_up_to_100(self):
        from rest_framework.exceptions import ValidationError

        day = datetime.date(2026, 4, 10)
        with self.assertRaisesMessage(ValidationError, "add up to 90"):
            charging.validate_installment_plan([
                {"name": "T1", "percent": D("50"), "due_date": day},
                {"name": "T2", "percent": D("40"), "due_date": day},
            ])

    def test_plan_names_must_differ_and_dates_be_in_order(self):
        from rest_framework.exceptions import ValidationError

        a, b = datetime.date(2026, 4, 10), datetime.date(2026, 8, 10)
        with self.assertRaises(ValidationError):
            charging.validate_installment_plan([{"name": "T1", "percent": D("50"), "due_date": a},
                                                {"name": "t1", "percent": D("50"), "due_date": b}])
        with self.assertRaises(ValidationError):
            charging.validate_installment_plan([{"name": "T1", "percent": D("50"), "due_date": b},
                                                {"name": "T2", "percent": D("50"), "due_date": a}])


class ConcessionMathTests(SimpleTestCase):
    def _c(self, kind, value):
        return SimpleNamespace(concession_type=SimpleNamespace(kind=kind, value=D(value)))

    def _lines(self, *amounts):
        return [charging.Line(None, f"L{i}", D(a), None) for i, a in enumerate(amounts)]

    def test_percent_applies_to_every_instalment(self):
        lines = self._lines("14400", "10800", "10800")
        self.assertEqual(charging.concession_discounts([self._c("percent", "10")], lines), [D("1440"), D("1080"), D("1080")])

    def test_fixed_amount_is_spread_and_adds_up_exactly(self):
        lines = self._lines("14400", "10800", "10800")
        out = charging.concession_discounts([self._c("fixed", "5000")], lines)
        self.assertEqual(sum(out), D("5000"))
        self.assertEqual(out[0], D("2000"))

    def test_discount_never_exceeds_the_fee(self):
        lines = self._lines("1000", "1000")
        out = charging.concession_discounts([self._c("percent", "80"), self._c("fixed", "5000")], lines)
        self.assertEqual(out, [D("1000"), D("1000")])


class ChargeApiTests(FeesFixtureMixin, TransactionTestCase):
    def setUp(self):
        super().setUp()
        with tenant_context(self.school):
            self.structure = FeeStructure.objects.create(
                fee_head=self.fee_head, academic_year="2026", level=self.section_a.level, amount=D("36000"),
            )
        self.client_ = self._client_as(self.owner_user)
        self.base = f"/api/fees/structures/{self.structure.id}"

    def _plan(self):
        return self.client_.put(f"{self.base}/installments/", {"installments": [
            {"name": "Term 1", "percent": "40", "due_date": "2026-04-10"},
            {"name": "Term 2", "percent": "30", "due_date": "2026-08-10"},
            {"name": "Term 3", "percent": "30", "due_date": "2026-12-10"},
        ]}, format="json", HTTP_HOST=self.DOMAIN)

    def _sibling_concession(self, student):
        with tenant_context(self.school):
            ctype = ConcessionType.objects.create(name="Sibling 10%", kind="percent", value=D("10"))
            StudentConcession.objects.create(student=student, concession_type=ctype, academic_year="2026")

    def test_charge_creates_one_fee_per_instalment_with_concession(self):
        self.assertEqual(self._plan().status_code, 200)
        self._sibling_concession(self.student1)

        preview = self.client_.get(f"{self.base}/charge/", HTTP_HOST=self.DOMAIN)
        self.assertEqual(preview.status_code, 200)
        self.assertEqual(preview.data["students_to_charge"], 2)
        self.assertEqual(preview.data["fees_to_create"], 6)
        self.assertEqual(preview.data["concession_total"], "3600.00")
        with tenant_context(self.school):
            self.assertFalse(StudentFee.objects.filter(fee_structure=self.structure).exists())

        resp = self.client_.post(f"{self.base}/charge/", HTTP_HOST=self.DOMAIN)
        self.assertEqual(resp.status_code, 201)
        with tenant_context(self.school):
            fees = list(StudentFee.objects.filter(student=self.student1, fee_structure=self.structure).order_by("due_date"))
            self.assertEqual([f.amount_due for f in fees], [D("14400"), D("10800"), D("10800")])
            self.assertEqual([f.discount_amount for f in fees], [D("1440"), D("1080"), D("1080")])
            self.assertEqual(fees[0].discount_reason, "Sibling 10%")
            self.assertEqual(fees[0].due_date, datetime.date(2026, 4, 10))
            self.assertEqual(get_outstanding_balance(fees[0]), D("12960"))
            other = StudentFee.objects.filter(student=self.student2, fee_structure=self.structure)
            self.assertEqual(sum(f.discount_amount for f in other), 0)

    def test_charging_again_creates_nothing(self):
        self._plan()
        self.client_.post(f"{self.base}/charge/", HTTP_HOST=self.DOMAIN)
        again = self.client_.post(f"{self.base}/charge/", HTTP_HOST=self.DOMAIN)
        self.assertEqual(again.data["fees_to_create"], 0)
        self.assertEqual(again.data["students_already_charged"], 2)
        with tenant_context(self.school):
            self.assertEqual(StudentFee.objects.filter(fee_structure=self.structure).count(), 6)

    def test_a_new_student_is_charged_only_on_the_next_run(self):
        self._plan()
        self.client_.post(f"{self.base}/charge/", HTTP_HOST=self.DOMAIN)
        newcomer = self._make_student("ENR-FE-9", "Nia", "New", self.section_a)
        with tenant_context(self.school):
            self.assertFalse(StudentFee.objects.filter(student=newcomer).exists())
        resp = self.client_.post(f"{self.base}/charge/", HTTP_HOST=self.DOMAIN)
        self.assertEqual(resp.data["students_to_charge"], 1)
        with tenant_context(self.school):
            self.assertEqual(StudentFee.objects.filter(student=newcomer).count(), 3)

    def test_structure_without_instalments_charges_once(self):
        resp = self.client_.post(f"{self.base}/charge/", HTTP_HOST=self.DOMAIN)
        self.assertEqual(resp.data["fees_to_create"], 2)
        with tenant_context(self.school):
            fee = StudentFee.objects.get(student=self.student1, fee_structure=self.structure)
            self.assertEqual(fee.amount_due, D("36000"))
            self.assertIsNone(fee.installment_id)

    def test_instalments_lock_once_students_are_charged(self):
        self._plan()
        self.client_.post(f"{self.base}/charge/", HTTP_HOST=self.DOMAIN)
        resp = self._plan()
        self.assertEqual(resp.status_code, 400)
        self.assertTrue(self.client_.get(f"{self.base}/installments/", HTTP_HOST=self.DOMAIN).data["locked"])

    def test_plan_not_adding_to_100_is_refused(self):
        resp = self.client_.put(f"{self.base}/installments/", {"installments": [
            {"name": "Term 1", "percent": "60", "due_date": "2026-04-10"},
        ]}, format="json", HTTP_HOST=self.DOMAIN)
        self.assertEqual(resp.status_code, 400)

    def test_students_of_other_classes_and_inactive_students_are_not_charged(self):
        with tenant_context(self.school):
            self.student2.status = "withdrawn"
            self.student2.save(update_fields=["status"])
        resp = self.client_.post(f"{self.base}/charge/", HTTP_HOST=self.DOMAIN)
        self.assertEqual(resp.data["students_total"], 1)

    def test_charging_needs_the_fee_structure_permission(self):
        client = self._client_as(self.random_staff_user)
        self.assertEqual(client.post(f"{self.base}/charge/", HTTP_HOST=self.DOMAIN).status_code, 403)
        self.assertEqual(client.get(f"{self.base}/charge/", HTTP_HOST=self.DOMAIN).status_code, 403)

    def test_charge_is_audited(self):
        from core.models import AuditLog

        self.client_.post(f"{self.base}/charge/", HTTP_HOST=self.DOMAIN)
        with tenant_context(self.school):
            self.assertTrue(AuditLog.objects.filter(action="fee_structure_charged").exists())


class ConcessionApiTests(FeesFixtureMixin, TransactionTestCase):
    def test_owner_sets_up_and_gives_a_concession(self):
        client = self._client_as(self.owner_user)
        t = client.post("/api/fees/concession-types/", {"name": "Staff child", "kind": "percent", "value": "50"},
                        format="json", HTTP_HOST=self.DOMAIN)
        self.assertEqual(t.status_code, 201, t.data)
        g = client.post("/api/fees/concessions/", {"student": str(self.student1.id), "concession_type": t.data["id"],
                                                  "academic_year": "2026", "note": "Mother teaches Class 3"},
                        format="json", HTTP_HOST=self.DOMAIN)
        self.assertEqual(g.status_code, 201, g.data)
        dup = client.post("/api/fees/concessions/", {"student": str(self.student1.id), "concession_type": t.data["id"],
                                                    "academic_year": "2026"}, format="json", HTTP_HOST=self.DOMAIN)
        self.assertEqual(dup.status_code, 400)
        listed = client.get(f"/api/fees/concessions/?student={self.student1.id}", HTTP_HOST=self.DOMAIN)
        rows = listed.data["results"] if isinstance(listed.data, dict) else listed.data
        self.assertEqual(rows[0]["concession_name"], "Staff child")

    def test_percent_over_100_is_refused(self):
        client = self._client_as(self.owner_user)
        resp = client.post("/api/fees/concession-types/", {"name": "Too much", "kind": "percent", "value": "150"},
                           format="json", HTTP_HOST=self.DOMAIN)
        self.assertEqual(resp.status_code, 400)

    def test_giving_a_concession_needs_the_fee_structure_permission(self):
        with tenant_context(self.school):
            ctype = ConcessionType.objects.create(name="Merit", kind="fixed", value=D("5000"))
        client = self._client_as(self.random_staff_user)
        resp = client.post("/api/fees/concessions/", {"student": str(self.student1.id), "concession_type": str(ctype.id),
                                                     "academic_year": "2026"}, format="json", HTTP_HOST=self.DOMAIN)
        self.assertEqual(resp.status_code, 403)

    def test_a_concession_cannot_be_deleted(self):
        with tenant_context(self.school):
            ctype = ConcessionType.objects.create(name="Merit", kind="fixed", value=D("5000"))
        client = self._client_as(self.owner_user)
        self.assertEqual(client.delete(f"/api/fees/concession-types/{ctype.id}/", HTTP_HOST=self.DOMAIN).status_code, 405)
