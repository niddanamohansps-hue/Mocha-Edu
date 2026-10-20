"""Stage F1: eSewa online-payment security.

Covers the three kinds of evidence an order can be moved by, and nothing else:
- T1: a signed browser callback (the public verify/callback endpoints);
- T2: the server-to-server status API, reached only through ``reconcile_online_payment_order``;
- T0: everything else, which must never change an order or be stored.

Also: server-built callback URLs, the minimal public response, generic errors and the dedicated
throttle. No real network request is ever made: the eSewa status call is mocked at
``fees.gateways._fetch_status_json`` (or ``fees.gateways._OPENER`` where the transport itself is
under test). eSewa's official contract could not be read in full when this was written, so
statuses whose meaning is uncertain (AMBIGUOUS, CANCELED, NOT_FOUND, the refund statuses) are
tested for the CONSERVATIVE behaviour only: they never create a payment, never fail an order and
never reverse one.

These tests create tenant schemas (and use threads), so they need a disposable PostgreSQL
database and are meant to be run only in an explicitly authorized isolated test stage.
"""

import base64
import datetime
import json
import threading
import urllib.error
import uuid as uuid_module
from decimal import Decimal
from unittest import mock

from django.core.cache import cache
from django.db import connection, connections
from django.test import TransactionTestCase, override_settings
from django.utils import timezone
from django_tenants.utils import schema_context, tenant_context
from rest_framework.test import APIClient
from rest_framework.throttling import ScopedRateThrottle

from organizations.models import Domain
from . import gateways
from .callbacks import build_callback_urls
from .gateways import (
    EsewaGatewayAdapter,
    PaymentConfigurationError,
    _decode_callback,
)
from .models import OnlinePaymentOrder, Payment, TenantPaymentGatewayConfig
from .services import (
    PaymentEvidenceRejected,
    assign_student_fee,
    initiate_online_payment_order,
    reconcile_online_payment_order,
    settle_online_payment_order,
)
from .tasks import reconcile_pending_online_payments
from .tests import FeesFixtureMixin

VERIFY_URL = "/api/fees/online/verify/"
CALLBACK_URL = "/api/fees/online/callback/"
INITIATE_URL = "/api/fees/online/initiate/"
GENERIC = PaymentEvidenceRejected.GENERIC_MESSAGE
SECRET = "test_esewa_secret_key_888"
MERCHANT = "TEST_SCHOOL_ESEWA"
SIGNED_ALL = "transaction_code,status,total_amount,transaction_uuid,product_code"
# Settings under which the production safety rules apply (the test runner forces DEBUG=False; the
# project's test flag is what normally switches them off).
PRODUCTION = dict(DEBUG=False, EDUSEKAI_ALLOW_DERIVED_TEST_DB=False, PASSWORD_RESET_FRONTEND_PROTOCOL="https")
PRODUCTION_FORM_URL = "https://epay.esewa.com.np/api/epay/main/v2/form"
FETCH = "fees.gateways._fetch_status_json"


class PaymentSecurityBase(FeesFixtureMixin, TransactionTestCase):
    def setUp(self):
        super().setUp()
        cache.clear()
        with tenant_context(self.school):
            self.fee1 = assign_student_fee(
                student=self.student1, fee_head=self.fee_head, academic_year="2026", amount_due=Decimal("1000.00")
            )
            cfg = TenantPaymentGatewayConfig.objects.create(gateway="esewa", merchant_code=MERCHANT, is_active=True)
            cfg.set_secret(SECRET)
            cfg.save()

    # ------------------------------------------------------------------ builders
    def _order(self, amount="500.00", gateway="esewa"):
        with tenant_context(self.school):
            order, _ = initiate_online_payment_order(
                student=self.student1,
                amount=Decimal(amount),
                allocations=[{"student_fee_id": self.fee1.id, "amount": Decimal(amount)}],
                gateway=gateway,
            )
        return order

    def _callback(self, order, *, status="COMPLETE", secret=SECRET, merchant=MERCHANT, uuid=None, amount=None,
                  signed=SIGNED_ALL, drop=(), extra=None, signature=None):
        payload = {
            "transaction_code": f"TX-{uuid_module.uuid4().hex[:8].upper()}",
            "status": status,
            "total_amount": amount or str(order.amount),
            "transaction_uuid": uuid or order.gateway_order_id,
            "product_code": merchant,
            "signed_field_names": signed,
        }
        message = ",".join(f"{field}={payload.get(field, '')}" for field in signed.split(","))
        payload["signature"] = signature or EsewaGatewayAdapter.generate_signature(secret, message)
        for key in drop:
            payload.pop(key, None)
        payload.update(extra or {})
        return base64.b64encode(json.dumps(payload).encode()).decode()

    def _status_response(self, order, **overrides):
        body = {
            "product_code": MERCHANT,
            "transaction_uuid": order.gateway_order_id,
            "total_amount": f"{order.amount:.2f}",
            "status": "COMPLETE",
            "ref_id": "0001TEST",
        }
        body.update(overrides)
        return {k: v for k, v in body.items() if v is not None}

    def _set_expiry(self, order, *, minutes_ago):
        with tenant_context(self.school):
            OnlinePaymentOrder.objects.filter(pk=order.pk).update(
                expires_at=timezone.now() - datetime.timedelta(minutes=minutes_ago)
            )

    def _reload(self, order):
        with tenant_context(self.school):
            return OnlinePaymentOrder.objects.get(pk=order.pk)

    def _payment_count(self):
        with tenant_context(self.school):
            return Payment.objects.count()

    def _verify(self, body=None, *, url=VERIFY_URL, **extra):
        return APIClient().post(url, body or {}, format="json", HTTP_HOST=self.DOMAIN, **extra)

    def _reconcile(self, order, response=None, side_effect=None):
        order = self._reload(order)
        patch = mock.patch(FETCH, return_value=response) if side_effect is None else mock.patch(FETCH, side_effect=side_effect)
        with patch as fetch, tenant_context(self.school):
            result = reconcile_online_payment_order(order)
        return result, fetch

    def _assert_untouched(self, order, payments_before=0):
        order = self._reload(order)
        self.assertEqual(order.status, "pending")
        self.assertEqual(order.gateway_response, {})
        self.assertEqual(order.gateway_reference, "")
        self.assertIsNone(order.payment_id)
        self.assertEqual(self._payment_count(), payments_before)


class UntrustedCallbackTests(PaymentSecurityBase):
    def test_untrusted_callbacks_change_nothing_store_nothing_and_get_one_generic_answer(self):
        order = self._order()
        oid = str(order.id)
        long_data = "A" * 9000
        variants = {
            "empty body": {},
            "order id only": {"order_id": oid},
            "transaction uuid only": {"transaction_uuid": order.gateway_order_id},
            "garbage data": {"data": "!!!not-base64!!!"},
            "non-json data": {"data": base64.b64encode(b"plain text").decode(), "order_id": oid},
            "json list": {"data": base64.b64encode(b"[1,2,3]").decode(), "order_id": oid},
            "oversized data": {"data": long_data, "order_id": oid},
            "bad signature": {"data": self._callback(order, secret="attacker-secret")},
            "no signature": {"data": self._callback(order, drop=("signature",))},
            "no signed_field_names": {"data": self._callback(order, drop=("signed_field_names",))},
            "status not signed": {"data": self._callback(order, signed="transaction_code,total_amount,transaction_uuid,product_code")},
            "amount not signed": {"data": self._callback(order, signed="transaction_code,status,transaction_uuid,product_code")},
            "uuid not signed": {"data": self._callback(order, signed="transaction_code,status,total_amount,product_code")},
            "product not signed": {"data": self._callback(order, signed="transaction_code,status,total_amount,transaction_uuid")},
            "transaction_code not signed": {"data": self._callback(order, signed="status,total_amount,transaction_uuid,product_code")},
            "signed field missing from payload": {"data": self._callback(order, drop=("transaction_code",))},
            "wrong merchant": {"data": self._callback(order, merchant="OTHER_MERCHANT")},
            "wrong transaction uuid": {"data": self._callback(order, uuid="someone-elses-transaction"), "order_id": oid},
            "amount mismatch": {"data": self._callback(order, amount="1.00")},
        }
        for name, body in variants.items():
            resp = self._verify(body)
            self.assertEqual(resp.status_code, 400, name)
            self.assertEqual(resp.data, {"error": GENERIC}, name)
            self._assert_untouched(order)
        # Also through the GET callback entry point, and with an unknown order.
        resp = APIClient().get(CALLBACK_URL, {"data": "garbage"}, HTTP_HOST=self.DOMAIN)
        self.assertEqual((resp.status_code, resp.data), (400, {"error": GENERIC}))
        resp = self._verify({"order_id": str(uuid_module.uuid4()), "data": self._callback(order)})
        self.assertEqual((resp.status_code, resp.data), (400, {"error": GENERIC}))
        self._assert_untouched(order)

    def test_rejection_does_not_say_which_check_failed(self):
        order = self._order()
        for body in ({"data": self._callback(order, secret="x")}, {"data": self._callback(order, merchant="X")},
                     {"data": self._callback(order, amount="1.00")}):
            resp = self._verify(body)
            text = json.dumps(resp.data, default=str).lower()
            for word in ("signature", "merchant", "amount", "hmac", SECRET.lower(), MERCHANT.lower(), order.gateway_order_id):
                self.assertNotIn(word, text)

    def test_a_plus_sign_turned_into_a_space_by_url_decoding_is_still_decoded(self):
        for n in range(3, 40):
            encoded = base64.b64encode(json.dumps({"k": ">" * n}).encode()).decode()
            if "+" in encoded:
                break
        self.assertIn("+", encoded)
        self.assertEqual(_decode_callback({"data": encoded.replace("+", " ")}), {"k": ">" * n})
        self.assertIsNone(_decode_callback({"data": "A" * (gateways.MAX_CALLBACK_CHARS + 1)}))
        self.assertIsNone(_decode_callback({"data": 12345}))
        self.assertIsNone(_decode_callback(None))

    def test_a_signed_callback_that_is_not_complete_leaves_the_order_alone(self):
        order = self._order()
        for status in ("PENDING", "AMBIGUOUS", "CANCELED", "NOT_FOUND", "FULL_REFUND", "SOMETHING_NEW"):
            resp = self._verify({"data": self._callback(order, status=status)})
            self.assertEqual(resp.status_code, 200, status)
            self.assertEqual(resp.data["status"], "pending", status)
            self._assert_untouched(order)


class CompleteCallbackTests(PaymentSecurityBase):
    def test_valid_complete_settles_once_stores_only_whitelisted_fields_and_replays_safely(self):
        order = self._order()
        data = self._callback(order)
        resp = self._verify({"data": data})
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data["status"], "success")
        self.assertTrue(resp.data["receipt_number"])
        self.assertEqual(self._payment_count(), 1)

        stored = self._reload(order)
        self.assertEqual(stored.status, "success")
        self.assertTrue(stored.gateway_reference.startswith("TX-"))
        self.assertEqual(
            set(stored.gateway_response),
            {"status", "transaction_code", "total_amount", "transaction_uuid", "product_code", "evidence", "verified_at"},
        )
        self.assertEqual(stored.gateway_response["evidence"], "callback")
        self.assertNotIn("signature", json.dumps(stored.gateway_response))

        again = self._verify({"data": data})
        self.assertEqual(again.data["status"], "already_completed")
        self.assertEqual(again.data["receipt_number"], resp.data["receipt_number"])
        self.assertEqual(self._payment_count(), 1)

    def test_extra_unsigned_fields_are_never_stored(self):
        order = self._order()
        resp = self._verify({"data": self._callback(order, extra={"note": "attacker text", "evil": {"a": 1}})})
        self.assertEqual(resp.status_code, 200)
        stored = self._reload(order)
        self.assertNotIn("attacker", json.dumps(stored.gateway_response))
        self.assertNotIn("evil", stored.gateway_response)

    def test_concurrent_complete_callbacks_create_exactly_one_payment(self):
        order = self._order()
        data = self._callback(order)
        barrier = threading.Barrier(3)
        results, errors = [], []

        def worker():
            try:
                with schema_context(self.SCHEMA_NAME):
                    barrier.wait(timeout=30)
                    results.append(
                        settle_online_payment_order(
                            order_id_or_gateway_order_id=order.id, raw_callback_payload={"data": data}
                        )["status"]
                    )
            except Exception as exc:  # noqa: BLE001 - reported below
                errors.append(repr(exc))
            finally:
                connections.close_all()

        threads = [threading.Thread(target=worker) for _ in range(3)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=90)
        self.assertEqual(errors, [])
        self.assertEqual(sorted(results), ["already_completed", "already_completed", "success"])
        self.assertEqual(self._payment_count(), 1)

    def test_a_confirmed_payment_arriving_after_the_order_was_closed_goes_to_staff(self):
        for closed in ("expired", "failed"):
            order = self._order(amount="200.00")
            with tenant_context(self.school):
                OnlinePaymentOrder.objects.filter(pk=order.pk).update(status=closed)
            before = self._payment_count()
            resp = self._verify({"data": self._callback(order)})
            self.assertEqual(resp.status_code, 200, closed)
            self.assertEqual(resp.data["status"], "reconciliation_required", closed)
            # Public callers get a fixed message; the specific reason stays on the order for staff.
            self.assertEqual(resp.data["reason"], "Payment requires additional verification.")
            stored = self._reload(order)
            self.assertEqual(stored.status, "reconciliation_required")
            self.assertIsNone(stored.payment_id)
            self.assertIn(closed, stored.reconciliation_reason)
            self.assertNotIn(closed, json.dumps(resp.data, default=str))
            self.assertEqual(self._payment_count(), before)  # no automatic payment, nothing discarded
            # A repeat changes nothing either.
            self.assertEqual(self._verify({"data": self._callback(order)}).data["status"], "reconciliation_required")
            self.assertEqual(self._payment_count(), before)

    def test_the_public_response_is_minimal(self):
        order = self._order()
        with tenant_context(self.school):
            OnlinePaymentOrder.objects.filter(pk=order.pk).update(created_by_user_id=self.student1_user.id)
        resp = self._verify({"data": self._callback(order)})
        self.assertEqual(set(resp.data), {"status", "order", "receipt_number", "reason"})
        self.assertEqual(set(resp.data["order"]), {"id", "gateway_order_id", "status", "amount", "payment"})
        raw = json.dumps(resp.data, default=str)
        for secret in ("Sam", "Pupil", str(self.student1.id), str(self.student1_user.id), "allocations", "gateway_response",
                       "signature", "student_fee_id", str(self.fee1.id)):
            self.assertNotIn(secret, raw)


class PublicReasonTests(PaymentSecurityBase):
    def test_a_reconciliation_required_result_never_exposes_fee_details_publicly(self):
        order = self._order(amount="400.00")
        # Interim counter payment leaves less outstanding than the online order intends to pay.
        with tenant_context(self.school):
            from .services import record_payment

            record_payment(
                student=self.student1, amount=Decimal("800.00"), method="cash",
                allocations=[{"student_fee_id": self.fee1.id, "amount": Decimal("800.00")}],
                recorded_by=self.finance_staff_member,
            )
        resp = self._verify({"data": self._callback(order)})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["status"], "reconciliation_required")
        self.assertEqual(resp.data["reason"], "Payment requires additional verification.")
        raw = json.dumps(resp.data, default=str)
        for leaked in (self.fee_head.name, "outstanding", "exceeds", "Allocation", "200.00", "800.00"):
            self.assertNotIn(leaked, raw)
        stored = self._reload(order)
        self.assertIn("exceeds current outstanding", stored.reconciliation_reason)  # staff still see the detail
        # Non-reconciliation results carry no reason at all.
        other = self._order(amount="100.00")
        self.assertEqual(self._verify({"data": self._callback(other, status="PENDING")}).data["reason"], "")


class StatusApiEvidenceTests(PaymentSecurityBase):
    def test_complete_from_the_status_api_settles_without_a_browser_hmac(self):
        order = self._order()
        response = self._status_response(order)
        self.assertNotIn("signature", response)  # the status response carries no browser-callback signature
        result, _ = self._reconcile(order, response)
        self.assertEqual(result["status"], "success")
        stored = self._reload(order)
        self.assertEqual((stored.status, stored.gateway_reference), ("success", "0001TEST"))
        self.assertEqual(stored.gateway_response["evidence"], "status_api")
        self.assertEqual(self._payment_count(), 1)
        # Replaying is a no-op and does not even ask the gateway.
        again, fetch = self._reconcile(order, response)
        self.assertEqual(again["status"], "success")
        fetch.assert_not_called()
        self.assertEqual(self._payment_count(), 1)

    def test_a_status_response_that_does_not_match_the_order_is_never_believed(self):
        mismatches = {
            "uuid": dict(transaction_uuid="another-transaction"),
            "merchant": dict(product_code="OTHER_MERCHANT"),
            "amount": dict(total_amount="1.00"),
            "uuid missing": dict(transaction_uuid=None),
            "merchant missing": dict(product_code=None),
            "amount missing": dict(total_amount=None),
        }
        for name, overrides in mismatches.items():
            order = self._order(amount="100.00")
            result, _ = self._reconcile(order, self._status_response(order, **overrides))
            self.assertEqual(result["status"], "pending", name)
            self.assertEqual(result["gateway_status"], "INVALID", name)
            self._assert_untouched(order, payments_before=self._payment_count())
        self.assertEqual(self._payment_count(), 0)

    def test_the_internal_trusted_path_rejects_anything_that_is_not_validated_status_evidence(self):
        from .services import settle_verified_gateway_payment

        order = self._reload(self._order())
        good = gateways.GatewayStatusResult(
            status="COMPLETE", transaction_uuid=order.gateway_order_id, total_amount=order.amount
        )
        bad_inputs = [
            {"data": "caller supplied dict"},
            gateways.GatewayStatusResult(status="PENDING", transaction_uuid=order.gateway_order_id, total_amount=order.amount),
            gateways.GatewayStatusResult(status="COMPLETE", evidence="callback", transaction_uuid=order.gateway_order_id, total_amount=order.amount),
            gateways.GatewayStatusResult(status="COMPLETE", transaction_uuid="other", total_amount=order.amount),
            gateways.GatewayStatusResult(status="COMPLETE", transaction_uuid=order.gateway_order_id, total_amount=Decimal("1.00")),
        ]
        with tenant_context(self.school):
            for bad in bad_inputs:
                with self.assertRaises(PaymentEvidenceRejected):
                    settle_verified_gateway_payment(order=order, status_result=bad)
            self.assertEqual(settle_verified_gateway_payment(order=order, status_result=good)["status"], "success")

    def test_pending_ambiguous_and_not_found_inside_the_grace_period_keep_the_order_recoverable(self):
        for status in ("PENDING", "AMBIGUOUS"):
            order = self._order()
            self._set_expiry(order, minutes_ago=300)  # long past expiry, well inside the 24h horizon
            result, _ = self._reconcile(order, self._status_response(order, status=status))
            self.assertEqual(result["status"], "pending", status)
            self.assertEqual(self._reload(order).status, "pending")
        order = self._order()
        self._set_expiry(order, minutes_ago=5)  # past expiry but inside the 15 minute grace
        result, _ = self._reconcile(order, {"status": "NOT_FOUND"})
        self.assertEqual(result["status"], "pending")
        order = self._order()  # not yet expired at all
        result, _ = self._reconcile(order, {"status": "NOT_FOUND"})
        self.assertEqual(result["status"], "pending")
        self.assertEqual(self._payment_count(), 0)

    def test_not_found_after_the_grace_period_expires_but_never_fails_the_order(self):
        order = self._order()
        self._set_expiry(order, minutes_ago=30)
        result, _ = self._reconcile(order, {"status": "NOT_FOUND"})
        self.assertEqual(result["status"], "expired")
        stored = self._reload(order)
        self.assertEqual(stored.status, "expired")
        self.assertIsNone(stored.payment_id)

    def test_canceled_and_refund_statuses_go_to_staff_and_never_create_or_reverse_a_payment(self):
        for status in ("CANCELED", "FULL_REFUND", "PARTIAL_REFUND"):
            order = self._order()
            result, _ = self._reconcile(order, self._status_response(order, status=status))
            self.assertEqual(result["status"], "reconciliation_required", status)
            stored = self._reload(order)
            self.assertEqual(stored.status, "reconciliation_required")
            self.assertTrue(stored.reconciliation_reason)
            self.assertIsNone(stored.payment_id)
        self.assertEqual(self._payment_count(), 0)

    def test_a_refund_status_never_touches_an_order_that_was_already_paid(self):
        order = self._order()
        self._reconcile(order, self._status_response(order))  # pay it
        self.assertEqual(self._payment_count(), 1)
        for status in ("FULL_REFUND", "CANCELED"):
            result, fetch = self._reconcile(order, self._status_response(order, status=status))
            self.assertEqual(result["status"], "success")
            fetch.assert_not_called()  # a settled order is not re-queried or reversed automatically
        self.assertEqual(self._payment_count(), 1)
        self.assertEqual(self._reload(order).status, "success")

    def test_transient_errors_and_unusable_responses_never_change_the_order(self):
        unusable = {
            "timeout": dict(side_effect=TimeoutError("timed out")),
            "connection": dict(side_effect=urllib.error.URLError("connection refused")),
            "http 500": dict(side_effect=urllib.error.HTTPError("https://x", 500, "boom", {}, None)),
            "http 302 (redirect refused)": dict(side_effect=urllib.error.HTTPError("https://x", 302, "Found", {}, None)),
            "bad json": dict(side_effect=json.JSONDecodeError("bad", "doc", 0)),
            "too large": dict(side_effect=ValueError("status response too large")),
            "list payload": dict(response=["not", "a", "dict"]),
            "string payload": dict(response="COMPLETE"),
            "unknown status": dict(response={"status": "SOMETHING_NEW"}),
            "service unavailable": dict(response={"code": 0, "error_message": "Service is currently unavailable"}),
        }
        for name, kwargs in unusable.items():
            order = self._order()
            self._set_expiry(order, minutes_ago=300)  # long past expiry; still inside the horizon
            result, _ = self._reconcile(order, **kwargs)
            self.assertEqual(result["status"], "pending", name)
            stored = self._reload(order)
            self.assertEqual((stored.status, stored.gateway_response), ("pending", {}), name)
        self.assertEqual(self._payment_count(), 0)

    def test_an_order_with_no_authoritative_answer_goes_to_staff_after_the_horizon_not_to_failed(self):
        order = self._order()
        self._set_expiry(order, minutes_ago=25 * 60)  # 25h past expiry, horizon is 24h
        result, _ = self._reconcile(order, side_effect=TimeoutError("down"))
        self.assertEqual(result["status"], "reconciliation_required")
        stored = self._reload(order)
        self.assertEqual(stored.status, "reconciliation_required")
        self.assertNotEqual(stored.status, "failed")
        self.assertIsNone(stored.payment_id)

    def test_a_payment_confirmed_after_the_order_was_closed_is_reconciled_not_lost(self):
        for closed in ("expired", "failed"):
            order = self._order(amount="100.00")
            with tenant_context(self.school):
                OnlinePaymentOrder.objects.filter(pk=order.pk).update(status=closed)
            before = self._payment_count()
            result, _ = self._reconcile(order, self._status_response(order))
            self.assertEqual(result["status"], "reconciliation_required", closed)
            self.assertEqual(self._payment_count(), before)

    def test_reconciliation_recovers_after_a_transient_error(self):
        order = self._order()
        self._set_expiry(order, minutes_ago=60)  # expired locally; the gateway was just unreachable
        first, _ = self._reconcile(order, side_effect=urllib.error.URLError("down"))
        self.assertEqual(first["status"], "pending")
        # The order has now passed its expiry, so a late confirmation is routed to staff rather than
        # silently creating money records for an order the system considers closed.
        second, _ = self._reconcile(order, self._status_response(order))
        self.assertEqual(second["status"], "reconciliation_required")

        fresh = self._order()  # a normal, unexpired order does settle after an earlier blip
        self.assertEqual(self._reconcile(fresh, side_effect=urllib.error.URLError("down"))[0]["status"], "pending")
        self.assertEqual(self._reconcile(fresh, self._status_response(fresh))[0]["status"], "success")
        self.assertEqual(self._payment_count(), 1)

    def test_the_periodic_task_processes_pending_orders_with_the_new_rules(self):
        order = self._order()
        self._set_expiry(order, minutes_ago=30)
        with mock.patch(FETCH, return_value={"status": "NOT_FOUND"}):
            summary = reconcile_pending_online_payments(batch_size=10, time_budget=30)
        self.assertEqual(summary["errors"], 0)
        self.assertEqual(self._reload(order).status, "expired")


class GatewayTransportTests(PaymentSecurityBase):
    class _FakeResponse:
        def __init__(self, body):
            self._body = body

        def read(self, n=-1):
            return self._body if n < 0 else self._body[:n]

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    def _query(self, order=None):
        order = self._reload(order or self._order())
        with tenant_context(self.school):
            return EsewaGatewayAdapter().query_status(order)

    def test_redirects_are_never_followed(self):
        handler = gateways._NoRedirectHandler()
        self.assertIsNone(handler.redirect_request(None, None, 302, "Found", {}, "https://evil.example.com/"))
        self.assertTrue(any(isinstance(h, gateways._NoRedirectHandler) for h in gateways._OPENER.handlers))

    def test_an_oversized_status_response_is_refused(self):
        big = b"{" + b" " * (gateways.MAX_STATUS_RESPONSE_BYTES + 10) + b"}"
        with mock.patch.object(gateways._OPENER, "open", return_value=self._FakeResponse(big)):
            self.assertEqual(self._query().status, "ERROR")
        ok = json.dumps({"status": "PENDING"}).encode()
        with mock.patch.object(gateways._OPENER, "open", return_value=self._FakeResponse(ok)):
            self.assertEqual(self._query().status, "PENDING")

    def test_the_status_url_must_be_https_on_an_esewa_host_and_not_a_test_host_in_production(self):
        order = self._order()
        cases = [
            # (settings, expected status, fetch expected to be called?)
            (dict(ESEWA_STATUS_URL="https://evil.example.com/api/epay/transaction/status/"), "ERROR", False),
            (dict(ESEWA_STATUS_URL="https://esewa.com.np.evil.example.com/status/"), "ERROR", False),
            (dict(ESEWA_STATUS_URL="https://user:pw@epay.esewa.com.np/status/"), "ERROR", False),
            (dict(ESEWA_STATUS_URL="ftp://epay.esewa.com.np/status/"), "ERROR", False),
            (dict(ESEWA_STATUS_URL="http://epay.esewa.com.np/status/", **PRODUCTION), "ERROR", False),
            (dict(ESEWA_STATUS_URL="https://rc.esewa.com.np/api/epay/transaction/status/", **PRODUCTION), "ERROR", False),
            (dict(ESEWA_STATUS_URL="https://epay.esewa.com.np/api/epay/transaction/status/", **PRODUCTION), "PENDING", True),
            (dict(ESEWA_STATUS_URL="https://rc.esewa.com.np/api/epay/transaction/status/"), "PENDING", True),  # test/dev run
        ]
        for overrides, expected, called in cases:
            with override_settings(**overrides), mock.patch(FETCH, return_value={"status": "PENDING"}) as fetch:
                self.assertEqual(self._query(order).status, expected, overrides)
                self.assertEqual(fetch.called, called, overrides)

    def test_production_refuses_the_test_merchant_and_test_endpoints_but_not_in_a_test_run(self):
        with tenant_context(self.school):
            TenantPaymentGatewayConfig.objects.filter(gateway="esewa").update(merchant_code="EPAYTEST")
        # Production form URL, so only the test MERCHANT is what gets refused here.
        with override_settings(ESEWA_URL=PRODUCTION_FORM_URL, **PRODUCTION):
            with tenant_context(self.school):
                with self.assertRaises(PaymentConfigurationError):
                    initiate_online_payment_order(
                        student=self.student1, amount=Decimal("10.00"),
                        allocations=[{"student_fee_id": self.fee1.id, "amount": Decimal("10.00")}], gateway="esewa",
                    )
                self.assertEqual(OnlinePaymentOrder.objects.count(), 0)  # nothing left behind
        # The same configuration is fine in a test run.
        self.assertEqual(self._order(amount="10.00").status, "pending")

    def test_production_refuses_the_default_test_form_endpoint(self):
        with override_settings(**PRODUCTION):
            with tenant_context(self.school):
                with self.assertRaises(PaymentConfigurationError):  # ESEWA_URL still defaults to the rc- test host
                    initiate_online_payment_order(
                        student=self.student1, amount=Decimal("10.00"),
                        allocations=[{"student_fee_id": self.fee1.id, "amount": Decimal("10.00")}], gateway="esewa",
                    )
                self.assertEqual(OnlinePaymentOrder.objects.count(), 0)

    def test_verification_with_unusable_configuration_is_a_generic_rejection_not_a_failure(self):
        order = self._order()
        with override_settings(**PRODUCTION):  # the tenant merchant is fine, but the callback URL host is irrelevant here
            with tenant_context(self.school):
                TenantPaymentGatewayConfig.objects.filter(gateway="esewa").update(merchant_code="EPAYTEST")
            resp = self._verify({"data": self._callback(order, merchant="EPAYTEST")})
        self.assertEqual((resp.status_code, resp.data), (400, {"error": GENERIC}))
        self._assert_untouched(order)


class CallbackUrlTests(PaymentSecurityBase):
    def _urls(self, kind="fees", school=None):
        with tenant_context(school or self.school):
            return build_callback_urls(kind)

    @override_settings(PASSWORD_RESET_FRONTEND_PROTOCOL="https", PASSWORD_RESET_FRONTEND_PORT="3555")
    def test_urls_use_the_tenants_primary_domain_and_fixed_paths(self):
        fees = self._urls("fees")
        self.assertEqual(fees.success_url, f"https://{self.DOMAIN}:3555/dashboard/fees/callback")
        self.assertEqual(fees.failure_url, f"https://{self.DOMAIN}:3555/dashboard/fees/callback?status=failed")
        parent = self._urls("parent_portal")
        self.assertEqual(parent.success_url, f"https://{self.DOMAIN}:3555/dashboard/parent-portal/fees/callback")
        self.assertTrue(parent.failure_url.endswith("/dashboard/parent-portal/fees/callback?status=failed"))
        with self.assertRaises(PaymentConfigurationError):
            self._urls("unknown")

    @override_settings(PASSWORD_RESET_FRONTEND_PROTOCOL="https", PASSWORD_RESET_FRONTEND_PORT="3555")
    def test_each_tenant_gets_its_own_domain(self):
        other = self._build_school(schema_name="fees_other_school", domain="otherschool.localhost", name="Other")
        try:
            self.assertIn("otherschool.localhost", self._urls("fees", other).success_url)
            self.assertNotIn("otherschool", self._urls("fees").success_url)
        finally:
            connection.set_schema_to_public()
            other.delete(force_drop=True)

    def test_production_scheme_and_port_rules(self):
        with override_settings(**PRODUCTION):  # PRODUCTION already pins the https protocol
            for port, expected in (("3555", ""), ("", ""), ("8443", ":8443")):
                with override_settings(PASSWORD_RESET_FRONTEND_PORT=port):
                    self.assertEqual(
                        self._urls().success_url, f"https://{self.DOMAIN}{expected}/dashboard/fees/callback", port
                    )
            with override_settings(PASSWORD_RESET_FRONTEND_PORT="abc"):
                with self.assertRaises(PaymentConfigurationError):
                    self._urls()
        with override_settings(**{**PRODUCTION, "PASSWORD_RESET_FRONTEND_PROTOCOL": "http"}, PASSWORD_RESET_FRONTEND_PORT=""):
            with self.assertRaises(PaymentConfigurationError):
                self._urls()
        with override_settings(PASSWORD_RESET_FRONTEND_PROTOCOL="http", PASSWORD_RESET_FRONTEND_PORT="3555"):
            self.assertTrue(self._urls().success_url.startswith("http://"))  # local development / test runs
        with override_settings(PASSWORD_RESET_FRONTEND_PROTOCOL="javascript", PASSWORD_RESET_FRONTEND_PORT=""):
            with self.assertRaises(PaymentConfigurationError):
                self._urls()

    def test_a_missing_or_invalid_primary_domain_fails_before_any_order_exists(self):
        def attempt():
            with tenant_context(self.school):
                return initiate_online_payment_order(
                    student=self.student1, amount=Decimal("10.00"),
                    allocations=[{"student_fee_id": self.fee1.id, "amount": Decimal("10.00")}], gateway="esewa",
                )

        connection.set_schema_to_public()
        Domain.objects.filter(tenant=self.school).update(is_primary=False)  # no primary domain
        with self.assertRaises(PaymentConfigurationError):
            attempt()
        Domain.objects.filter(tenant=self.school).update(is_primary=True, domain="bad_host!.localhost")  # not a valid host name
        with self.assertRaises(PaymentConfigurationError):
            attempt()
        self.assertEqual(self._order_count(), 0)

    def _order_count(self):
        with tenant_context(self.school):
            return OnlinePaymentOrder.objects.count()

    @override_settings(PASSWORD_RESET_FRONTEND_PROTOCOL="https", PASSWORD_RESET_FRONTEND_PORT="3555")
    def test_client_urls_and_spoofed_headers_are_ignored_by_the_api(self):
        self._give_role_only(self.student1_user, ["pay_own_fees"])
        client = self._client_as(self.student1_user)
        body = {
            "student": str(self.student1.id), "amount": "100.00", "gateway": "esewa",
            "allocations": [{"student_fee": str(self.fee1.id), "amount": "100.00"}],
            "return_url": "https://evil.example.com/steal", "failure_url": "https://evil.example.com/steal?x=1",
        }
        resp = client.post(
            INITIATE_URL, body, format="json", HTTP_HOST=self.DOMAIN,
            HTTP_X_FORWARDED_HOST="evil.example.com", HTTP_ORIGIN="https://evil.example.com", HTTP_REFERER="https://evil.example.com/",
        )
        self.assertEqual(resp.status_code, 201, resp.data)
        params = resp.data["gateway_payload"]["form_parameters"]
        self.assertEqual(params["success_url"], f"https://{self.DOMAIN}:3555/dashboard/fees/callback")
        self.assertEqual(params["failure_url"], f"https://{self.DOMAIN}:3555/dashboard/fees/callback?status=failed")
        self.assertNotIn("evil", json.dumps(resp.data, default=str))

    @override_settings(PASSWORD_RESET_FRONTEND_PROTOCOL="https", PASSWORD_RESET_FRONTEND_PORT="3555")
    def test_the_parent_workflow_uses_the_parent_callback_path(self):
        self._give_role_only(self.parent1_user, ["pay_child_fees"])
        client = self._client_as(self.parent1_user)
        resp = client.post(
            f"/api/parent-portal/children/{self.student1.id}/pay-fees/",
            {"amount": "50.00", "gateway": "esewa", "allocations": [{"student_fee": str(self.fee1.id), "amount": "50.00"}],
             "return_url": "https://evil.example.com/", "failure_url": "https://evil.example.com/"},
            format="json", HTTP_HOST=self.DOMAIN,
        )
        self.assertEqual(resp.status_code, 201, resp.data)
        params = resp.data["gateway_payload"]["form_parameters"]
        self.assertTrue(params["success_url"].endswith("/dashboard/parent-portal/fees/callback"))
        self.assertTrue(params["failure_url"].endswith("/dashboard/parent-portal/fees/callback?status=failed"))
        self.assertNotIn("evil", json.dumps(resp.data, default=str))


class GenericErrorTests(PaymentSecurityBase):
    LEAK = "SECRET-INTERNAL-DETAIL-9917"

    def test_public_and_authenticated_errors_never_contain_exception_text(self):
        order = self._order()
        with mock.patch("fees.views.settle_online_payment_order", side_effect=RuntimeError(self.LEAK)):
            resp = self._verify({"order_id": str(order.id)})
        self.assertEqual((resp.status_code, resp.data), (400, {"error": GENERIC}))

        self._give_role_only(self.student1_user, ["pay_own_fees"])
        client = self._client_as(self.student1_user)
        body = {"student": str(self.student1.id), "amount": "10.00", "gateway": "esewa",
                "allocations": [{"student_fee": str(self.fee1.id), "amount": "10.00"}]}
        with mock.patch("fees.views.initiate_online_payment_order", side_effect=PaymentConfigurationError(self.LEAK)):
            resp = client.post(INITIATE_URL, body, format="json", HTTP_HOST=self.DOMAIN)
        self.assertEqual(resp.status_code, 503)
        self.assertNotIn(self.LEAK, json.dumps(resp.data, default=str))

        self._give_role_only(self.parent1_user, ["pay_child_fees"])
        parent = self._client_as(self.parent1_user)
        with mock.patch("fees.gateways.get_gateway_credentials", side_effect=PaymentConfigurationError(self.LEAK)):
            resp = parent.post(
                f"/api/parent-portal/children/{self.student1.id}/pay-fees/",
                {"amount": "10.00", "gateway": "esewa", "allocations": [{"student_fee": str(self.fee1.id), "amount": "10.00"}]},
                format="json", HTTP_HOST=self.DOMAIN,
            )
        self.assertEqual(resp.status_code, 503)
        self.assertNotIn(self.LEAK, json.dumps(resp.data, default=str))

        self._give_role_only(self.finance_user, ["collect_payments"])
        staff = self._client_as(self.finance_user)
        with mock.patch("fees.views.reconcile_online_payment_order", side_effect=RuntimeError(self.LEAK)):
            resp = staff.post(f"/api/fees/online/orders/{order.id}/reconcile/", {}, format="json", HTTP_HOST=self.DOMAIN)
        self.assertEqual(resp.status_code, 400)
        self.assertNotIn(self.LEAK, json.dumps(resp.data, default=str))


class VerifyThrottleTests(PaymentSecurityBase):
    def test_the_dedicated_scope_exists_in_production_and_test_configuration(self):
        self.assertIn("online_payment_verify", ScopedRateThrottle.THROTTLE_RATES)
        self.assertEqual(ScopedRateThrottle.THROTTLE_RATES["online_payment_verify"], "1000/min")  # test-mode override
        from django.conf import settings

        self.assertEqual(settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]["online_payment_verify"], "1000/min")

    def test_requests_over_the_limit_get_429_on_both_public_entry_points_per_client(self):
        cache.clear()
        rates = {**ScopedRateThrottle.THROTTLE_RATES, "online_payment_verify": "3/min"}
        with mock.patch.object(ScopedRateThrottle, "THROTTLE_RATES", rates):
            statuses = [self._verify({}, REMOTE_ADDR="10.9.9.1").status_code for _ in range(5)]
            self.assertEqual(statuses, [400, 400, 400, 429, 429])
            # The callback (GET) entry point shares the scope, so it is limited too.
            self.assertEqual(
                APIClient().get(CALLBACK_URL, {}, HTTP_HOST=self.DOMAIN, REMOTE_ADDR="10.9.9.1").status_code, 429
            )
            # A different client address is unaffected.
            self.assertEqual(self._verify({}, REMOTE_ADDR="10.9.9.2").status_code, 400)

    def test_the_reconciliation_task_is_not_throttled(self):
        cache.clear()
        with tenant_context(self.school):
            order, _ = initiate_online_payment_order(
                student=self.student1, amount=Decimal("300.00"),
                allocations=[{"student_fee_id": self.fee1.id, "amount": Decimal("300.00")}], gateway="mock",
            )
        rates = {**ScopedRateThrottle.THROTTLE_RATES, "online_payment_verify": "1/min"}
        with mock.patch.object(ScopedRateThrottle, "THROTTLE_RATES", rates):
            for _ in range(3):
                self._verify({}, REMOTE_ADDR="10.9.9.3")  # exhausts the public bucket
            summary = reconcile_pending_online_payments(batch_size=10, time_budget=30)
        self.assertEqual((summary["errors"], summary["success"]), (0, 1))
        self.assertEqual(self._reload(order).status, "success")
