"""Regression tests for the expenses review fixes: the school's own calendar day, fee reversals,
payroll in the summary, one account per kind receiving fees, and collision-free numbering."""
import datetime
import threading
import uuid as uuid_module
from decimal import Decimal
from zoneinfo import ZoneInfo

from django.db import connection, connections
from django.test import TransactionTestCase, override_settings
from django_tenants.utils import tenant_context

from fees.models import Payment
from organizations.models import Domain, Organization
from payroll.models import PayrollRun, Payslip
from profiles.models import Profile
from staff.models import StaffMember
from students.models import Student

from .models import Expense, ExpenseCategory, PaymentAccount
from .services import generate_voucher_number, get_day_book, get_income_vs_expense_summary
from .signals import seed_default_expense_data

IST = ZoneInfo("Asia/Kolkata")


@override_settings(ALERT_TIME_ZONE="Asia/Kolkata")
class ExpensesReviewFixesTest(TransactionTestCase):
    def setUp(self):
        suffix = uuid_module.uuid4().hex[:8]
        connection.set_schema_to_public()
        self.school = Organization.objects.create(schema_name=f"expr_{suffix}", name="Expenses Review School")
        Domain.objects.create(domain=f"expr-{suffix}.localhost", tenant=self.school, is_primary=True)
        with tenant_context(self.school):
            seed_default_expense_data(type("FakeSender", (), {"name": "expenses"})())
            self.cash = PaymentAccount.objects.get(is_default=True)
            profile = Profile.objects.create(
                first_name="Meera", last_name="Iyer", gender="female", date_of_birth=datetime.date(2012, 1, 1)
            )
            self.student = Student.objects.create(
                profile=profile, enrollment_id=f"ADM-{suffix}", admission_date=datetime.date(2024, 4, 1)
            )

    def _payment(self, amount, method="cash", status="completed", at=None, reverses=None):
        payment = Payment.objects.create(
            student=self.student,
            amount=Decimal(amount),
            method=method,
            status=status,
            receipt_number=f"R-{uuid_module.uuid4().hex[:10]}",
            reverses=reverses,
        )
        if at is not None:
            Payment.objects.filter(pk=payment.pk).update(created_at=at)
            payment.refresh_from_db()
        return payment

    def test_early_morning_ist_payment_belongs_to_the_school_day(self):
        """02:00 IST on 15 June is 20:30 UTC on 14 June: the day book for the 15th must show it, with local time."""
        with tenant_context(self.school):
            self._payment("500.00", at=datetime.datetime(2026, 6, 15, 2, 0, tzinfo=IST))
            on_15th = get_day_book(datetime.date(2026, 6, 15), self.cash.id)
            on_14th = get_day_book(datetime.date(2026, 6, 14), self.cash.id)
            self.assertEqual(on_15th["total_inflow"], "500.00")
            self.assertEqual(on_15th["entries"][0]["time_str"], "02:00 AM")
            self.assertEqual(on_14th["total_inflow"], "0.00")
            summary = get_income_vs_expense_summary("2026-06-15", "2026-06-15")
            self.assertEqual(summary["total_income"], "500.00")

    def test_a_reversed_fee_receipt_is_netted_out(self):
        with tenant_context(self.school):
            day = datetime.datetime(2026, 7, 1, 11, 0, tzinfo=IST)
            original = self._payment("1000.00", at=day)
            self._payment("1000.00", status="reversed", at=day.replace(hour=12), reverses=original)
            book = get_day_book(datetime.date(2026, 7, 1), self.cash.id)
            self.assertEqual(book["total_inflow"], "1000.00")
            self.assertEqual(book["total_outflow"], "1000.00")
            self.assertEqual(book["closing_balance"], book["opening_balance"])
            self.assertEqual(get_income_vs_expense_summary("2026-07-01", "2026-07-01")["total_income"], "0.00")
            # The next day opens with the reversal taken into account.
            self.assertEqual(
                get_day_book(datetime.date(2026, 7, 2), self.cash.id)["opening_balance"], f"{self.cash.opening_balance:.2f}"
            )

    def test_fees_are_credited_to_one_bank_account_only(self):
        with tenant_context(self.school):
            first = PaymentAccount.objects.create(name="Bank A", account_type="bank", is_default=False)
            second = PaymentAccount.objects.create(name="Bank B", account_type="bank", is_default=False)
            self._payment("750.00", method="upi", at=datetime.datetime(2026, 8, 3, 10, 0, tzinfo=IST))
            totals = [
                Decimal(get_day_book(datetime.date(2026, 8, 3), a.id)["total_inflow"]) for a in (first, second)
            ]
            self.assertEqual(sorted(totals), [Decimal("0.00"), Decimal("750.00")])

    def test_approved_payroll_is_counted_as_an_expense(self):
        with tenant_context(self.school):
            run = PayrollRun.objects.create(
                year=2026, month=9, period_start=datetime.date(2026, 9, 1), period_end=datetime.date(2026, 9, 30),
                status="paid",
            )
            teacher = StaffMember.objects.create(
                profile=Profile.objects.create(
                    first_name="Ravi", last_name="Nair", gender="male", date_of_birth=datetime.date(1985, 1, 1)
                ),
                employee_id=f"E-{uuid_module.uuid4().hex[:6]}",
                designation="Teacher",
            )
            Payslip.objects.create(
                run=run, staff=teacher, employee_id=teacher.employee_id, staff_name="Ravi Nair",
                basic_amount=Decimal("30000"), gross_amount=Decimal("32000"), deductions_amount=Decimal("2000"),
                net_amount=Decimal("30000"), working_days=26,
            )
            summary = get_income_vs_expense_summary("2026-09-01", "2026-09-30")
            self.assertEqual(summary["total_expenses"], "30000.00")

    def test_concurrent_voucher_numbers_do_not_collide(self):
        category = None
        with tenant_context(self.school):
            category = ExpenseCategory.objects.first()
        errors, numbers = [], []

        def create_one():
            try:
                with tenant_context(self.school):
                    from django.db import transaction

                    with transaction.atomic():
                        number = generate_voucher_number(datetime.date(2026, 10, 1))
                        Expense.objects.create(
                            voucher_number=number, category=category, amount=Decimal("10.00"),
                            expense_date=datetime.date(2026, 10, 1), paid_to="Vendor", payment_account=self.cash,
                        )
                        numbers.append(number)
            except Exception as exc:  # noqa: BLE001 - the test reports whatever went wrong
                errors.append(repr(exc))
            finally:
                connections.close_all()

        threads = [threading.Thread(target=create_one) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(errors, [])
        self.assertEqual(len(set(numbers)), 4)
