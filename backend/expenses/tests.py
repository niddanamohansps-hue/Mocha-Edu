import datetime
from decimal import Decimal
import uuid as uuid_module

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TransactionTestCase
from django_tenants.utils import tenant_context
from rest_framework.test import APIRequestFactory, force_authenticate

from academics.models import AcademicYear
from organizations.models import Domain, Organization
from roles.models import Role, UserRole
from roles.signals import seed_default_roles

from .models import Expense, ExpenseCategory, PaymentAccount, CashbookEntry
from .serializers import ExpenseSerializer, CashbookEntrySerializer
from .services import (
    generate_voucher_number,
    generate_entry_number,
    get_day_book,
    get_income_vs_expense_summary,
)
from .signals import seed_default_expense_data
from .views import (
    ExpenseViewSet,
    CashbookEntryViewSet,
    CashbookDayBookView,
    IncomeVsExpenseSummaryView,
    ExpenseExportCsvView,
)

User = get_user_model()


class ExpensesFixtureMixin:
    def _build_school(self, schema_name=None, domain=None, name="Expenses Test School"):
        suffix = uuid_module.uuid4().hex[:8]
        schema_name = schema_name or f"exp_{suffix}"
        domain = domain or f"exp-{suffix}.localhost"
        connection.set_schema_to_public()
        school = Organization.objects.create(schema_name=schema_name, name=name)
        Domain.objects.create(domain=domain, tenant=school, is_primary=True)
        return school


class ExpensesIntegrationTest(ExpensesFixtureMixin, TransactionTestCase):
    def setUp(self):
        self.school = self._build_school()
        self.factory = APIRequestFactory()

        with tenant_context(self.school):
            seed_default_roles()
            seed_default_expense_data(type("FakeSender", (), {"name": "expenses"})())

            self.ay, _ = AcademicYear.objects.get_or_create(
                name="2026-27",
                defaults={
                    "start_date": datetime.date(2026, 4, 1),
                    "end_date": datetime.date(2027, 3, 31),
                    "is_current": True,
                },
            )

            # Create an Owner user
            self.owner_user = User.objects.create_user(
                username=f"owner_{uuid_module.uuid4().hex[:6]}@school.com",
                email="owner@school.com",
                password="OwnerPassword123!",
            )
            owner_role = Role.objects.get(slug="owner")
            UserRole.objects.create(user=self.owner_user, role=owner_role)

            # Create an unprivileged user (e.g. basic staff without expense permissions)
            self.plain_user = User.objects.create_user(
                username=f"staff_{uuid_module.uuid4().hex[:6]}@school.com",
                email="staff@school.com",
                password="StaffPassword123!",
            )

    def test_default_categories_and_account_seeded(self):
        with tenant_context(self.school):
            # Check default categories
            cats = ExpenseCategory.objects.all()
            self.assertGreaterEqual(cats.count(), 8)
            cat_codes = set(cats.values_list("code", flat=True))
            self.assertIn("TRANS", cat_codes)
            self.assertIn("UTIL", cat_codes)
            self.assertIn("MAINT", cat_codes)
            self.assertIn("ACAD", cat_codes)
            self.assertIn("WELFARE", cat_codes)

            # Check default Cash Account
            acc = PaymentAccount.objects.filter(is_default=True).first()
            self.assertIsNotNone(acc)
            self.assertEqual(acc.name, "Main Cash Counter")
            self.assertEqual(acc.account_type, PaymentAccount.AccountType.CASH)

    def test_expense_voucher_creation_and_auto_numbering(self):
        with tenant_context(self.school):
            cat = ExpenseCategory.objects.get(code="TRANS")
            cash_acc = PaymentAccount.objects.filter(is_default=True).first()

            # Sequence generator check
            v1_num = generate_voucher_number(datetime.date(2026, 6, 1))
            self.assertTrue(v1_num.startswith("EXP-2026-"))

            # Create via serializer
            data = {
                "category": str(cat.id),
                "payment_account": str(cash_acc.id),
                "amount": "4500.00",
                "expense_date": "2026-06-15",
                "payment_method": "cash",
                "paid_to": "HP Petrol Pump",
                "reference_number": "BILL-90812",
                "description": "Bus 1 and Bus 2 Diesel fill-up",
                "status": "approved",
            }
            serializer = ExpenseSerializer(data=data)
            self.assertTrue(serializer.is_valid(), serializer.errors)
            exp = serializer.save()

            self.assertEqual(exp.amount, Decimal("4500.00"))
            self.assertEqual(exp.paid_to, "HP Petrol Pump")
            self.assertEqual(exp.status, Expense.Status.APPROVED)
            self.assertTrue(exp.voucher_number.startswith("EXP-2026-"))

            # Create second expense
            data2 = {
                "category": str(cat.id),
                "payment_account": str(cash_acc.id),
                "amount": "1200.00",
                "expense_date": "2026-06-16",
                "paid_to": "Tyre Care",
            }
            s2 = ExpenseSerializer(data=data2)
            self.assertTrue(s2.is_valid())
            exp2 = s2.save()
            self.assertNotEqual(exp.voucher_number, exp2.voucher_number)

    def test_expense_approval_and_cancellation(self):
        with tenant_context(self.school):
            cat = ExpenseCategory.objects.get(code="UTIL")
            cash_acc = PaymentAccount.objects.filter(is_default=True).first()

            # Create draft expense
            exp = Expense.objects.create(
                voucher_number="EXP-2026-0099",
                category=cat,
                payment_account=cash_acc,
                amount=Decimal("1500.00"),
                expense_date=datetime.date(2026, 7, 10),
                paid_to="Local Electrician",
                status=Expense.Status.DRAFT,
            )
            self.assertEqual(exp.status, Expense.Status.DRAFT)

            # ViewSet approve action
            view = ExpenseViewSet.as_view({"post": "approve"})
            req = self.factory.post(f"/api/expenses/vouchers/{exp.id}/approve/")
            req.tenant = self.school
            force_authenticate(req, user=self.owner_user)

            resp = view(req, pk=str(exp.id))
            self.assertEqual(resp.status_code, 200)
            exp.refresh_from_db()
            self.assertEqual(exp.status, Expense.Status.APPROVED)

            # ViewSet cancel action
            view_cancel = ExpenseViewSet.as_view({"post": "cancel"})
            req_c = self.factory.post(
                f"/api/expenses/vouchers/{exp.id}/cancel/",
                {"reason": "Duplicate bill entered by mistake"},
            )
            req_c.tenant = self.school
            force_authenticate(req_c, user=self.owner_user)

            resp_c = view_cancel(req_c, pk=str(exp.id))
            self.assertEqual(resp_c.status_code, 200)
            exp.refresh_from_db()
            self.assertEqual(exp.status, Expense.Status.CANCELLED)
            self.assertEqual(exp.cancellation_reason, "Duplicate bill entered by mistake")
            self.assertIsNotNone(exp.cancelled_at)

    def test_cashbook_entry_and_contra_transfer(self):
        with tenant_context(self.school):
            cash_acc = PaymentAccount.objects.filter(is_default=True).first()
            bank_acc = PaymentAccount.objects.create(
                name="SBI School Account",
                account_type=PaymentAccount.AccountType.BANK,
                bank_name="State Bank of India",
                account_number="1234567890",
                opening_balance=Decimal("50000.00"),
            )

            # 1. Direct Income
            inc_data = {
                "entry_type": CashbookEntry.EntryType.INCOME,
                "amount": "2500.00",
                "entry_date": "2026-08-01",
                "to_account": str(cash_acc.id),
                "source_or_payee": "Prospectus & Admission Form Sales",
                "payment_method": "cash",
            }
            s_inc = CashbookEntrySerializer(data=inc_data)
            self.assertTrue(s_inc.is_valid(), s_inc.errors)
            e_inc = s_inc.save()
            self.assertTrue(e_inc.entry_number.startswith("INC-2026-"))
            self.assertEqual(e_inc.amount, Decimal("2500.00"))

            # 2. Contra Transfer (Cash deposited to Bank)
            trf_data = {
                "entry_type": CashbookEntry.EntryType.TRANSFER,
                "amount": "15000.00",
                "entry_date": "2026-08-01",
                "from_account": str(cash_acc.id),
                "to_account": str(bank_acc.id),
                "source_or_payee": "Cash Deposit Counter Slip #441",
                "payment_method": "cash",
            }
            s_trf = CashbookEntrySerializer(data=trf_data)
            self.assertTrue(s_trf.is_valid(), s_trf.errors)
            e_trf = s_trf.save()
            self.assertTrue(e_trf.entry_number.startswith("TRF-2026-"))

            # 3. Reject same source and destination
            bad_trf = {
                "entry_type": CashbookEntry.EntryType.TRANSFER,
                "amount": "1000.00",
                "from_account": str(cash_acc.id),
                "to_account": str(cash_acc.id),
                "source_or_payee": "Self transfer",
            }
            s_bad = CashbookEntrySerializer(data=bad_trf)
            self.assertFalse(s_bad.is_valid())

    def test_day_book_reconciliation_math(self):
        with tenant_context(self.school):
            test_date = datetime.date(2026, 9, 15)
            cash_acc = PaymentAccount.objects.filter(is_default=True).first()
            cash_acc.opening_balance = Decimal("10000.00")
            cash_acc.save()

            bank_acc = PaymentAccount.objects.create(
                name="HDFC School Account",
                account_type=PaymentAccount.AccountType.BANK,
            )

            cat_fuel = ExpenseCategory.objects.get(code="TRANS")
            cat_util = ExpenseCategory.objects.get(code="UTIL")

            # 1. Direct Income today into cash counter (+2,500)
            CashbookEntry.objects.create(
                entry_number="INC-2026-0001",
                entry_type=CashbookEntry.EntryType.INCOME,
                amount=Decimal("2500.00"),
                entry_date=test_date,
                to_account=cash_acc,
                source_or_payee="Uniform Sale Counter",
                payment_method="cash",
            )

            # 2. Approved Expense today from cash counter (-3,000)
            Expense.objects.create(
                voucher_number="EXP-2026-0010",
                category=cat_fuel,
                payment_account=cash_acc,
                amount=Decimal("3000.00"),
                expense_date=test_date,
                paid_to="Diesel Station",
                status=Expense.Status.APPROVED,
                payment_method="cash",
            )

            # 3. Another approved expense (-1,000)
            Expense.objects.create(
                voucher_number="EXP-2026-0011",
                category=cat_util,
                payment_account=cash_acc,
                amount=Decimal("1000.00"),
                expense_date=test_date,
                paid_to="Water Tanker",
                status=Expense.Status.APPROVED,
                payment_method="cash",
            )

            # 4. Transfer out to Bank (-5,000)
            CashbookEntry.objects.create(
                entry_number="TRF-2026-0001",
                entry_type=CashbookEntry.EntryType.TRANSFER,
                amount=Decimal("5000.00"),
                entry_date=test_date,
                from_account=cash_acc,
                to_account=bank_acc,
                source_or_payee="Bank Deposit Slip #12",
                payment_method="cash",
            )

            # 5. Cancelled expense on same day should NOT affect cash balance
            Expense.objects.create(
                voucher_number="EXP-2026-0012",
                category=cat_util,
                payment_account=cash_acc,
                amount=Decimal("9999.00"),
                expense_date=test_date,
                paid_to="Cancelled Bill",
                status=Expense.Status.CANCELLED,
            )

            # Compute Day Book
            day_book = get_day_book(test_date, cash_acc.id)

            self.assertEqual(day_book["opening_balance"], "10000.00")
            self.assertEqual(day_book["total_inflow"], "2500.00")
            self.assertEqual(day_book["total_outflow"], "9000.00")  # 3000 + 1000 + 5000 = 9000
            # Closing = 10000 + 2500 - 9000 = 3500.00
            self.assertEqual(day_book["closing_balance"], "3500.00")
            self.assertEqual(len(day_book["entries"]), 4)

            # Check running balance on the last entry
            self.assertEqual(day_book["entries"][-1]["running_balance"], 3500.00)

    def test_income_vs_expense_summary_and_csv_export(self):
        with tenant_context(self.school):
            from_d = datetime.date(2026, 10, 1)
            to_d = datetime.date(2026, 10, 31)

            cat = ExpenseCategory.objects.get(code="ACAD")
            cash_acc = PaymentAccount.objects.filter(is_default=True).first()

            # Record expense
            Expense.objects.create(
                voucher_number="EXP-2026-0501",
                category=cat,
                payment_account=cash_acc,
                amount=Decimal("8000.00"),
                expense_date=datetime.date(2026, 10, 10),
                paid_to="Stationery Press",
                status=Expense.Status.APPROVED,
            )

            # Record non-fee income
            CashbookEntry.objects.create(
                entry_number="INC-2026-0501",
                entry_type=CashbookEntry.EntryType.INCOME,
                amount=Decimal("12000.00"),
                entry_date=datetime.date(2026, 10, 5),
                to_account=cash_acc,
                source_or_payee="Annual Day Sponsorship",
            )

            summary = get_income_vs_expense_summary(from_d, to_d)
            self.assertIn("total_income", summary)
            self.assertIn("total_expenses", summary)
            self.assertEqual(summary["direct_income"], "12000.00")
            self.assertEqual(summary["operating_expenses"], "8000.00")
            self.assertEqual(summary["net_surplus"], "4000.00")
            self.assertGreaterEqual(len(summary["category_breakdown"]), 1)

            # Test CSV Export View
            view = ExpenseExportCsvView.as_view()
            req = self.factory.get("/api/expenses/reports/export/?from_date=2026-10-01&to_date=2026-10-31")
            req.tenant = self.school
            force_authenticate(req, user=self.owner_user)

            resp = view(req)
            self.assertEqual(resp.status_code, 200)
            self.assertIn("text/csv", resp["Content-Type"])
            csv_content = resp.content.decode("utf-8-sig")
            self.assertIn("VOUCHER_NO,DATE_YYYY_MM_DD,CATEGORY", csv_content)
            self.assertIn("EXP-2026-0501", csv_content)
            self.assertIn("Stationery Press", csv_content)
            self.assertIn("8000.00", csv_content)

    def test_expense_permissions_enforcement(self):
        with tenant_context(self.school):
            cat = ExpenseCategory.objects.first()
            cash_acc = PaymentAccount.objects.filter(is_default=True).first()

            # Plain user without record_expenses should get 403 Forbidden on create
            view = ExpenseViewSet.as_view({"post": "create"})
            req = self.factory.post(
                "/api/expenses/vouchers/",
                {
                    "category": str(cat.id),
                    "payment_account": str(cash_acc.id),
                    "amount": "500.00",
                    "paid_to": "Test Shop",
                },
            )
            req.tenant = self.school
            force_authenticate(req, user=self.plain_user)

            resp = view(req)
            self.assertEqual(resp.status_code, 403)

            # Owner user with view_expenses and record_expenses succeeds
            req_owner = self.factory.post(
                "/api/expenses/vouchers/",
                {
                    "category": str(cat.id),
                    "payment_account": str(cash_acc.id),
                    "amount": "500.00",
                    "paid_to": "Test Shop",
                },
            )
            req_owner.tenant = self.school
            force_authenticate(req_owner, user=self.owner_user)

            resp_owner = view(req_owner)
            self.assertEqual(resp_owner.status_code, 201)

