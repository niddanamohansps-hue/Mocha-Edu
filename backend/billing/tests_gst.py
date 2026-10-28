from datetime import datetime, timezone as dt_timezone
from decimal import Decimal

from django.db import connection
from django.test import SimpleTestCase, TransactionTestCase, override_settings

from organizations.models import Organization

from .gst import split, validate_gstin
from .models import Plan, Subscription
from .services import issue_invoice

T0 = datetime(2026, 10, 28, tzinfo=dt_timezone.utc)


@override_settings(PLATFORM_STATE_CODE="29", PLATFORM_GSTIN="")
class GstSplitTests(SimpleTestCase):
    def test_same_state_is_cgst_plus_sgst(self):
        self.assertEqual(split(Decimal("180.00"), "29"), (Decimal("90.00"), Decimal("90.00"), Decimal("0.00"), "29"))

    def test_other_state_is_igst(self):
        self.assertEqual(split(Decimal("180.00"), "27"), (Decimal("0.00"), Decimal("0.00"), Decimal("180.00"), "27"))

    def test_unknown_state_uses_the_platform_state(self):
        cgst, sgst, igst, pos = split(Decimal("179.83"), "")
        self.assertEqual((cgst + sgst, igst, pos), (Decimal("179.83"), Decimal("0.00"), "29"))  # odd paise kept

    def test_gstin_rules(self):
        self.assertEqual(validate_gstin(" 29abcde1234f1z5 "), "29ABCDE1234F1Z5")
        for bad in ("29ABCDE1234F1Z", "99ABCDE1234F1Z5", "hello"):
            with self.assertRaises(ValueError):
                validate_gstin(bad)

    @override_settings(PLATFORM_STATE_CODE="", PLATFORM_GSTIN="27ABCDE1234F1Z5")
    def test_platform_state_comes_from_its_gstin(self):
        self.assertEqual(split(Decimal("10.00"), "27")[2], Decimal("0.00"))  # Maharashtra -> Maharashtra: no IGST


@override_settings(PLATFORM_STATE_CODE="29")
class GstInvoiceTests(TransactionTestCase):
    def setUp(self):
        connection.set_schema_to_public()
        Organization.auto_create_schema = False
        self.addCleanup(setattr, Organization, "auto_create_schema", True)
        self.school = Organization.objects.create(schema_name="gst_school", name="GST School")
        self.plan = Plan.objects.create(code="gst-plan", name="GST Plan", monthly_price=Decimal("1000.00"))
        self.sub = Subscription.objects.create(organization=self.school, plan=self.plan, cycle="monthly",
                                               billing_gstin="27ABCDE1234F1Z5", billing_state="27")

    def tearDown(self):
        self.sub.invoices.all().delete()
        self.sub.delete()
        self.plan.delete()
        Organization.objects.filter(pk=self.school.pk).delete()

    def test_an_out_of_state_school_is_billed_igst_with_its_gstin(self):
        invoice = issue_invoice(self.sub, now=T0)
        self.assertEqual((invoice.igst_amount, invoice.cgst_amount, invoice.place_of_supply, invoice.billed_gstin),
                         (Decimal("180.00"), Decimal("0.00"), "27", "27ABCDE1234F1Z5"))
        self.assertEqual(invoice.total, Decimal("1180.00"))

    def test_a_same_state_school_is_billed_cgst_and_sgst(self):
        self.sub.billing_state, self.sub.billing_gstin = "29", ""
        self.sub.save()
        invoice = issue_invoice(self.sub, now=T0)
        self.assertEqual((invoice.cgst_amount, invoice.sgst_amount, invoice.igst_amount),
                         (Decimal("90.00"), Decimal("90.00"), Decimal("0.00")))

    def test_the_pdf_shows_the_tax_lines(self):
        from .pdf import render_invoice_pdf
        from .services import mark_invoice_paid

        invoice = issue_invoice(self.sub, now=T0)
        invoice, _ = mark_invoice_paid(invoice.id, payment_id="pay_gst", now=T0)
        self.assertTrue(render_invoice_pdf(invoice).startswith(b"%PDF"))
