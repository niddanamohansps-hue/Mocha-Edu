"""Pay links in fee reminders: the signed token, the public pay page's API, and the reminders that carry the link."""
from datetime import timedelta
from decimal import Decimal
from unittest import mock

from django.contrib.auth.models import AnonymousUser
from django.test import override_settings
from django_tenants.utils import tenant_context
from rest_framework.test import APIRequestFactory

from families.models import Parent
from notifications.models import EmailOutboxEvent, Notification, WhatsAppOutboxEvent
from students.models import Student

from . import paylinks
from .models import FeeHead, OnlinePaymentOrder
from .paylink_views import PayLinkDetailView, PayLinkStartView
from .tests_reminders import DUE, ReminderFixture


class PayLinkBase(ReminderFixture):
    def _call(self, view, method, token, data=None):
        factory = APIRequestFactory()
        request = factory.get("/x/") if method == "get" else factory.post("/x/", data or {}, format="json")
        request.tenant = self.school
        request.user = AnonymousUser()
        with tenant_context(self.school):
            return view.as_view()(request, token=token)

    def _token(self, student=None):
        with tenant_context(self.school):
            return paylinks.make_token((student or self.student).id)

    def _transport_fee(self, amount="500.00"):
        with tenant_context(self.school):
            head = FeeHead.objects.get_or_create(name="Transport")[0]
        return self._fee(self.school, self.student, amount=amount, head=head)


class TokenTests(PayLinkBase):
    def test_a_valid_token_names_its_student_and_forged_expired_or_inactive_ones_name_nobody(self):
        token = self._token()
        with tenant_context(self.school):
            self.assertEqual(paylinks.student_from_token(token).id, self.student.id)
            self.assertIsNone(paylinks.student_from_token(token[:-3] + "xyz"))
            self.assertIsNone(paylinks.student_from_token("not-a-token"))
            with mock.patch.object(paylinks, "PAY_LINK_MAX_AGE_SECONDS", -1):
                self.assertIsNone(paylinks.student_from_token(token))
            Student.objects.filter(pk=self.student.pk).update(status="inactive")
            self.assertIsNone(paylinks.student_from_token(token))

    def test_a_token_from_another_use_of_signing_is_not_accepted(self):
        from django.core import signing

        other = signing.dumps({"s": str(self.student.id)}, salt="something.else")
        with tenant_context(self.school):
            self.assertIsNone(paylinks.student_from_token(other))


class ScheduledJobLinkTests(PayLinkBase):
    def test_a_link_built_inside_schema_context_still_carries_the_schools_own_domain(self):
        """Scheduled jobs enter a school with schema_context(), which leaves a bare placeholder as the tenant."""
        from django_tenants.utils import schema_context

        with tenant_context(self.school):
            expected = paylinks.pay_url(self.student)
        with schema_context(self.school.schema_name):
            built = paylinks.pay_url(self.student)
        self.assertEqual(built.split("/pay/")[0], expected.split("/pay/")[0])
        self.assertTrue(built.startswith("http"), built)


class DetailTests(PayLinkBase):
    def test_the_page_lists_only_what_is_still_owed_for_that_student(self):
        transport = self._transport_fee()
        self._pay(self.school, transport, "200")  # 300 left
        self._pay(self.school, self.fee, "1500")  # tuition fully paid
        stranger = self._student(self.school, "ENR-R-7")
        self._fee(self.school, stranger, amount="999.00")

        response = self._call(PayLinkDetailView, "get", self._token())
        self.assertEqual(response.status_code, 200)
        self.assertEqual([(f["fee_head"], f["outstanding"]) for f in response.data["fees"]], [("Transport", Decimal("300.00"))])
        self.assertEqual(response.data["total"], Decimal("300.00"))
        self.assertEqual(response.data["student"], "FirstENR-R-1 Last")
        self.assertEqual(response.data["school"], self.SCHEMA_A)

    def test_a_bad_link_is_a_plain_404(self):
        self.assertEqual(self._call(PayLinkDetailView, "get", "forged").status_code, 404)
        self.assertEqual(self._call(PayLinkStartView, "post", "forged").status_code, 404)

    @override_settings(FEES_PAY_LINK_GATEWAY="razorpay")
    def test_without_a_working_gateway_the_page_says_so_and_nothing_can_be_started(self):
        detail = self._call(PayLinkDetailView, "get", self._token())
        self.assertFalse(detail.data["available"])
        started = self._call(PayLinkStartView, "post", self._token())
        self.assertEqual(started.status_code, 503)
        with tenant_context(self.school):
            self.assertEqual(OnlinePaymentOrder.objects.count(), 0)


@override_settings(FEES_PAY_LINK_GATEWAY="mock")
class StartTests(PayLinkBase):
    def test_starting_creates_one_ordinary_order_for_everything_owed(self):
        self._transport_fee()
        response = self._call(PayLinkStartView, "post", self._token())
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["amount"], Decimal("2000.00"))
        self.assertEqual(response.data["gateway_payload"]["gateway"], "mock")
        with tenant_context(self.school):
            order = OnlinePaymentOrder.objects.get()
            self.assertEqual((order.amount, order.status, order.student_id), (Decimal("2000.00"), "pending", self.student.id))
            self.assertIsNone(order.created_by_user_id)  # nobody was logged in
            self.assertEqual({a["student_fee_id"] for a in order.allocations_snapshot}, {str(self.fee.id), str(self._transport_fee_id())})

    def _transport_fee_id(self):
        from .models import StudentFee

        with tenant_context(self.school):
            return StudentFee.objects.get(fee_head__name="Transport").id

    def test_the_parent_can_pay_just_some_of_the_fees_and_each_is_paid_at_its_current_balance(self):
        transport = self._transport_fee()
        self._pay(self.school, self.fee, "500")  # 1000 of the tuition is left
        response = self._call(PayLinkStartView, "post", self._token(), {"fees": [str(self.fee.id)]})
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["amount"], Decimal("1000.00"))
        with tenant_context(self.school):
            order = OnlinePaymentOrder.objects.get()
            self.assertEqual(order.allocations_snapshot, [{"student_fee_id": str(self.fee.id), "amount": "1000.00"}])

    def test_a_fee_that_is_not_theirs_or_not_owed_is_refused_and_creates_nothing(self):
        stranger = self._student(self.school, "ENR-R-7")
        theirs_not = self._fee(self.school, stranger, amount="999.00")
        response = self._call(PayLinkStartView, "post", self._token(), {"fees": [str(theirs_not.id)]})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self._call(PayLinkStartView, "post", self._token(), {"fees": "everything"}).status_code, 400)
        self._pay(self.school, self.fee, "1500")
        nothing_left = self._call(PayLinkStartView, "post", self._token())
        self.assertEqual(nothing_left.status_code, 400)
        with tenant_context(self.school):
            self.assertEqual(OnlinePaymentOrder.objects.count(), 0)


class ReminderTests(PayLinkBase):
    def _bodies(self):
        with tenant_context(self.school):
            return [e.body for e in EmailOutboxEvent.objects.all()], list(Notification.objects.all())

    @override_settings(FEES_PAY_LINK_GATEWAY="mock")
    def test_email_and_in_app_reminders_carry_the_pay_link_when_the_school_takes_online_payments(self):
        self._run(self.school, DUE - timedelta(days=2))
        bodies, notes = self._bodies()
        self.assertEqual(len(bodies), 2)
        for body in bodies:
            self.assertIn("Pay online: http", body)
            self.assertIn("/pay/", body)
        token = bodies[0].split("/pay/")[1].split()[0]
        with tenant_context(self.school):
            self.assertEqual(paylinks.student_from_token(token).id, self.student.id)
        self.assertTrue(all(n.link.startswith("/pay/") for n in notes))

    @override_settings(FEES_PAY_LINK_GATEWAY="razorpay")
    def test_without_online_payment_the_reminders_are_exactly_as_before(self):
        self._run(self.school, DUE - timedelta(days=2))
        bodies, notes = self._bodies()
        self.assertEqual(len(bodies), 2)
        self.assertTrue(all("Pay online" not in b for b in bodies))
        self.assertTrue(all(not n.link.startswith("/pay/") for n in notes))

    def _opt_in_whatsapp(self):
        with tenant_context(self.school):
            parent = Parent.objects.get()
            parent.profile.phone = "9876543210"
            parent.profile.save()
            parent.whatsapp_opt_in = True
            parent.save()

    @override_settings(WHATSAPP_PROVIDER="console", FEES_PAY_LINK_GATEWAY="mock")
    def test_the_whatsapp_reminder_ends_with_the_pay_link(self):
        self._opt_in_whatsapp()
        self._run(self.school, DUE - timedelta(days=2))
        with tenant_context(self.school):
            params = WhatsAppOutboxEvent.objects.get().params
        self.assertEqual(len(params), 5)
        self.assertTrue(params[4].startswith("http") and "/pay/" in params[4])

    @override_settings(WHATSAPP_PROVIDER="console", FEES_PAY_LINK_GATEWAY="razorpay")
    def test_without_online_payment_the_whatsapp_reminder_points_at_the_school_site(self):
        self._opt_in_whatsapp()
        self._run(self.school, DUE - timedelta(days=2))
        with tenant_context(self.school):
            params = WhatsAppOutboxEvent.objects.get().params
        self.assertEqual(len(params), 5)
        self.assertTrue(params[4].endswith("/login"))
