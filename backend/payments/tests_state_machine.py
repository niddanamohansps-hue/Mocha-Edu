"""Stage F2b: the signup-payment state machine, subdomain reservation, resumable provisioning,
late payments and the legacy-state migration.

Most tests patch ``provision_organization`` (no tenant schema is created). The two tests that
exercise the real provisioning create one small tenant each and drop it afterwards.
"""
import importlib
from datetime import timedelta
from unittest import mock

from django.apps import apps as django_apps
from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import override_settings
from django.utils import timezone

from accounts.provisioning import ProvisioningError, provision_organization
from accounts.serializers import OrganizationRegisterSerializer
from accounts.utils.crypto import decrypt_secret
from organizations.models import Domain, Organization
from roles.models import UserRole
from . import services
from .admin import PaymentAdmin
from .models import Payment
from .tests_security import GENERIC, PROVISION, SECRET, SignupPaymentTestBase

SETUP_FAILED = {
    "error": "Your payment was received, but we could not finish setting up your institution. "
    "Please contact support."
}


def fake_provision(domain_url="http://school.test/login"):
    """A stand-in for provision_organization that 'creates' the public organization."""
    def fake(**kwargs):
        organization = Organization.objects.get(schema_name="public")
        callback = kwargs.get("on_organization_created")
        if kwargs.get("organization") is None and callback:
            callback(organization)
        return {"organization": organization, "domain_url": domain_url}
    return fake


@override_settings(ESEWA_CLIENT_SECRET=SECRET)
class ReservationTests(SignupPaymentTestBase):
    def test_init_sets_an_expiry_from_the_configured_ttl(self):
        with override_settings(SIGNUP_PAYMENT_TTL_MINUTES=30):
            payment = self.make_payment()
        remaining = payment.expires_at - timezone.now()
        self.assertGreater(remaining, timedelta(minutes=29))
        self.assertLessEqual(remaining, timedelta(minutes=30))
        self.assertEqual(payment.status, Payment.PENDING)

    def test_a_reserved_subdomain_cannot_be_started_twice(self):
        self.make_payment()
        resp = self.init(username="someoneelse", email="else@f2b.example")
        self.assertEqual(resp.status_code, 400)
        self.assertIn("subdomain", resp.data)
        self.assertEqual(Payment.objects.count(), 1)

    def test_an_expired_reservation_releases_the_subdomain(self):
        old = self.make_payment()
        Payment.objects.filter(pk=old.pk).update(expires_at=timezone.now() - timedelta(minutes=1))
        resp = self.init(username="someoneelse", email="else@f2b.example")
        self.assertEqual(resp.status_code, 200, getattr(resp, "data", None))
        old.refresh_from_db()
        self.assertEqual(old.status, Payment.EXPIRED)
        self.assertEqual(Payment.objects.filter(status=Payment.PENDING).count(), 1)

    def test_a_paid_signup_keeps_its_subdomain_even_after_the_expiry_time(self):
        payment = self.make_payment()
        Payment.objects.filter(pk=payment.pk).update(status=Payment.PAID, expires_at=timezone.now() - timedelta(hours=2))
        resp = self.init(username="someoneelse", email="else@f2b.example")
        self.assertEqual(resp.status_code, 400)

    def test_database_allows_only_one_reserving_row_per_subdomain(self):
        self.make_payment()
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Payment.objects.create(amount="500", organization_name="x", subdomain="f2a_school",
                                       email="a@b.example", phone="1", password="x")

    def test_expired_and_provisioned_rows_do_not_reserve(self):
        for status in (Payment.EXPIRED, Payment.PROVISIONED, Payment.FAILED):
            Payment.objects.create(amount="500", organization_name="x", subdomain="free_name",
                                   email="a@b.example", phone="1", password="x", status=status)
        Payment.objects.create(amount="500", organization_name="x", subdomain="free_name",
                               email="a@b.example", phone="1", password="x")  # still allowed


@override_settings(ESEWA_CLIENT_SECRET=SECRET)
class StateMachineTests(SignupPaymentTestBase):
    def setUp(self):
        super().setUp()
        self.payment = self.make_payment()

    def verify_payment(self, **kwargs):
        return self.verify(self.callback(self.payment, **kwargs))

    def reload(self):
        self.payment.refresh_from_db()
        return self.payment

    def test_success_records_the_money_and_the_institution(self):
        with mock.patch(PROVISION, side_effect=fake_provision()):
            resp = self.verify_payment()
        self.assertEqual(resp.status_code, 200)
        payment = self.reload()
        self.assertEqual(payment.status, Payment.PROVISIONED)
        self.assertIsNotNone(payment.paid_at)
        self.assertIsNotNone(payment.provisioned_at)
        self.assertEqual(payment.gateway_reference, "TEST-CODE")
        self.assertEqual(payment.provisioning_attempts, 1)
        self.assertEqual(payment.organization.schema_name, "public")
        self.assertEqual(payment.failure_code, "")

    def test_the_stored_password_is_discarded_once_provisioned(self):
        self.assertEqual(decrypt_secret(self.payment.password), "OwnerPass123!")
        with mock.patch(PROVISION, side_effect=fake_provision()):
            self.verify_payment()
        self.assertEqual(self.reload().password, "")

    def test_a_failure_keeps_the_money_recorded_and_the_data_for_a_retry(self):
        with mock.patch(PROVISION, side_effect=RuntimeError("db down")):
            resp = self.verify_payment()
        self.assertEqual(resp.status_code, 500)
        self.assertEqual(resp.data, SETUP_FAILED)
        payment = self.reload()
        self.assertEqual(payment.status, Payment.PROVISIONING_FAILED)
        self.assertEqual(payment.failure_code, "unexpected_error")
        self.assertIsNotNone(payment.paid_at)
        self.assertEqual(decrypt_secret(payment.password), "OwnerPass123!")

    def test_reloading_the_return_page_retries_and_succeeds(self):
        with mock.patch(PROVISION, side_effect=RuntimeError("db down")):
            self.verify_payment()
        with mock.patch(PROVISION, side_effect=fake_provision()):
            resp = self.verify_payment()
        self.assertEqual(resp.status_code, 200, getattr(resp, "data", None))
        payment = self.reload()
        self.assertEqual(payment.status, Payment.PROVISIONED)
        self.assertEqual(payment.provisioning_attempts, 2)
        self.assertEqual(payment.failure_code, "")

    def test_a_retry_resumes_with_the_institution_an_earlier_attempt_created(self):
        created = []

        def first(**kwargs):
            organization = Organization.objects.get(schema_name="public")
            kwargs["on_organization_created"](organization)
            created.append(organization)
            raise RuntimeError("failed after creating the tenant")

        with mock.patch(PROVISION, side_effect=first):
            self.verify_payment()
        self.assertEqual(self.reload().organization_id, created[0].pk)

        with mock.patch(PROVISION, side_effect=fake_provision()) as second:
            self.verify_payment()
        self.assertEqual(second.call_args.kwargs["organization"].pk, created[0].pk)

    def test_a_permanent_failure_is_reported_as_a_client_error(self):
        error = ProvisioningError("subdomain_taken", "This subdomain is already taken.")
        with mock.patch(PROVISION, side_effect=error):
            resp = self.verify_payment()
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.data, SETUP_FAILED)
        payment = self.reload()
        self.assertEqual(payment.status, Payment.PROVISIONING_FAILED)
        self.assertEqual(payment.failure_code, "subdomain_taken")

    def test_a_fresh_provisioning_claim_is_not_taken_over(self):
        Payment.objects.filter(pk=self.payment.pk).update(status=Payment.PROVISIONING)
        with mock.patch(PROVISION) as provision:
            resp = self.verify_payment()
        self.assertEqual(resp.status_code, 202)
        provision.assert_not_called()

    def test_a_stalled_provisioning_claim_is_recovered(self):
        Payment.objects.filter(pk=self.payment.pk).update(
            status=Payment.PROVISIONING, updated_at=timezone.now() - timedelta(hours=1)
        )
        with mock.patch(PROVISION, side_effect=fake_provision()):
            resp = self.verify_payment()
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(self.reload().status, Payment.PROVISIONED)

    def test_only_one_caller_can_claim_a_payment(self):
        Payment.objects.filter(pk=self.payment.pk).update(status=Payment.PAID)
        self.assertEqual(services._claim_for_provisioning(self.payment.pk), 1)
        self.assertEqual(services._claim_for_provisioning(self.payment.pk), 0)
        self.assertEqual(self.reload().provisioning_attempts, 1)

    def test_repeated_callbacks_after_success_do_not_provision_again(self):
        with mock.patch(PROVISION, side_effect=fake_provision()) as provision:
            self.verify_payment()
            resp = self.verify_payment()
        self.assertEqual(resp.status_code, 200)
        self.assertIn("already processed", resp.data["message"])
        self.assertEqual(provision.call_count, 1)

    def test_a_non_complete_status_changes_nothing(self):
        resp = self.verify_payment(status="PENDING")
        self.assertEqual(resp.status_code, 400)
        payment = self.reload()
        self.assertEqual(payment.status, Payment.PENDING)
        self.assertIsNone(payment.paid_at)

    def test_a_forged_callback_never_marks_paid(self):
        resp = self.verify_payment(secret="wrong")
        self.assertEqual(resp.data, GENERIC)
        self.assertEqual(self.reload().status, Payment.PENDING)


@override_settings(ESEWA_CLIENT_SECRET=SECRET)
class LatePaymentTests(SignupPaymentTestBase):
    def setUp(self):
        super().setUp()
        self.payment = self.make_payment()
        Payment.objects.filter(pk=self.payment.pk).update(
            status=Payment.EXPIRED, expires_at=timezone.now() - timedelta(hours=3)
        )

    def reload(self):
        self.payment.refresh_from_db()
        return self.payment

    def test_money_that_arrives_after_expiry_is_honoured(self):
        with mock.patch(PROVISION, side_effect=fake_provision()):
            resp = self.verify(self.callback(self.payment))
        self.assertEqual(resp.status_code, 200, getattr(resp, "data", None))
        payment = self.reload()
        self.assertEqual(payment.status, Payment.PROVISIONED)
        self.assertIsNotNone(payment.paid_at)

    def test_late_money_after_the_data_was_discarded_is_flagged_for_a_person(self):
        Payment.objects.filter(pk=self.payment.pk).update(password="")
        with mock.patch(PROVISION) as provision:
            resp = self.verify(self.callback(self.payment))
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.data, SETUP_FAILED)
        provision.assert_not_called()
        payment = self.reload()
        self.assertEqual(payment.status, Payment.EXPIRED)
        self.assertEqual(payment.failure_code, "data_discarded")
        self.assertIsNotNone(payment.paid_at)
        self.assertEqual(payment.gateway_reference, "TEST-CODE")

    def test_late_money_for_a_subdomain_someone_else_now_holds_is_flagged(self):
        other = Payment.objects.create(amount="500", organization_name="Other", subdomain=self.payment.subdomain,
                                       email="o@o.example", phone="1", password="x")
        with mock.patch(PROVISION) as provision:
            resp = self.verify(self.callback(self.payment))
        self.assertEqual(resp.status_code, 400)
        provision.assert_not_called()
        payment = self.reload()
        self.assertEqual(payment.status, Payment.EXPIRED)
        self.assertEqual(payment.failure_code, "subdomain_taken")
        self.assertIsNotNone(payment.paid_at)
        other.refresh_from_db()
        self.assertEqual(other.status, Payment.PENDING)


@override_settings(ESEWA_CLIENT_SECRET=SECRET)
class RealProvisioningTests(SignupPaymentTestBase):
    """Creates real tenants (schema DDL); each test drops what it made."""

    def tearDown(self):
        for org in Organization.objects.filter(schema_name__in=["f2b_resume", "f2b_checks"]):
            org.delete(force_drop=True)
        super().tearDown()

    def test_a_failure_after_the_tenant_exists_is_resumed_without_duplicates(self):
        payment = self.make_payment(subdomain="f2b_resume", username="resumeowner", email="resume@f2b.example")
        with mock.patch("accounts.provisioning.Domain.objects.get_or_create", side_effect=RuntimeError("boom")):
            resp = self.verify(self.callback(payment))
        self.assertEqual(resp.status_code, 500)
        payment.refresh_from_db()
        self.assertEqual(payment.status, Payment.PROVISIONING_FAILED)
        self.assertIsNotNone(payment.organization_id, "the tenant created before the failure must be recorded")
        self.assertEqual(Organization.objects.filter(schema_name="f2b_resume").count(), 1)

        resp = self.verify(self.callback(payment))
        self.assertEqual(resp.status_code, 200, getattr(resp, "data", None))
        payment.refresh_from_db()
        self.assertEqual(payment.status, Payment.PROVISIONED)
        self.assertEqual(payment.password, "")
        self.assertEqual(Organization.objects.filter(schema_name="f2b_resume").count(), 1)
        organization = Organization.objects.get(schema_name="f2b_resume")
        self.assertEqual(Domain.objects.filter(tenant=organization, is_primary=True).count(), 1)
        user = get_user_model().objects.get(email="resume@f2b.example")
        from django_tenants.utils import tenant_context
        with tenant_context(organization):
            self.assertEqual(UserRole.objects.filter(user=user, role__slug="owner").count(), 1)

    def test_known_problems_are_found_before_a_tenant_is_created(self):
        get_user_model().objects.create_user(username="taken", email="t@f2b.example", password="RealPass123!")
        before = Organization.objects.count()
        cases = {
            "subdomain_taken": dict(subdomain="public"),
            "password_mismatch": dict(email="t@f2b.example", password="WrongPass123!"),
            "username_taken": dict(username="taken", email="new@f2b.example"),
        }
        for code, overrides in cases.items():
            with self.subTest(code):
                kwargs = dict(organization_name="X", subdomain="f2b_checks", username="newowner",
                              email="n@f2b.example", password="OwnerPass123!")
                kwargs.update(overrides)
                with self.assertRaises(ProvisioningError) as raised:
                    provision_organization(**kwargs)
                self.assertEqual(raised.exception.code, code)
        self.assertEqual(Organization.objects.count(), before)

    def test_the_registration_serializer_still_creates_through_the_shared_code(self):
        error = ProvisioningError("subdomain_taken", "This subdomain is already taken.")
        serializer = OrganizationRegisterSerializer(data=self.registration(subdomain="f2b_checks"))
        self.assertTrue(serializer.is_valid(), serializer.errors)
        with mock.patch("accounts.serializers.provision_organization", side_effect=error):
            from rest_framework.exceptions import ValidationError
            with self.assertRaises(ValidationError):
                serializer.save()


class LegacyMigrationTests(SignupPaymentTestBase):
    def run_migration(self):
        module = importlib.import_module("payments.migrations.0004_migrate_legacy_payment_states")
        module.migrate_states(django_apps, None)

    def legacy(self, subdomain, status, **extra):
        return Payment.objects.create(amount="500", organization_name="Legacy", subdomain=subdomain,
                                      email="l@l.example", phone="1", password="enc", status=status, **extra)

    def test_completed_rows_are_mapped_by_whether_the_institution_exists(self):
        with_org = self.legacy("public", "COMPLETED")
        without_org = self.legacy("never_created", "COMPLETED")
        self.run_migration()
        with_org.refresh_from_db()
        without_org.refresh_from_db()
        self.assertEqual(with_org.status, Payment.PROVISIONED)
        self.assertEqual(with_org.password, "")
        self.assertEqual(without_org.status, Payment.PROVISIONING_FAILED)
        self.assertEqual(without_org.failure_code, "legacy_no_institution")
        self.assertEqual(without_org.password, "enc")  # kept so it can be retried

    def test_pending_rows_get_an_expiry_and_stale_ones_expire(self):
        fresh = self.legacy("fresh_one", "PENDING")
        stale = self.legacy("stale_one", "PENDING")
        Payment.objects.filter(pk=stale.pk).update(created_at=timezone.now() - timedelta(days=2))
        self.run_migration()
        fresh.refresh_from_db()
        stale.refresh_from_db()
        self.assertEqual(fresh.status, Payment.PENDING)
        self.assertIsNotNone(fresh.expires_at)
        self.assertEqual(stale.status, Payment.EXPIRED)


class AdminTests(SignupPaymentTestBase):
    def test_the_stored_password_is_not_exposed_and_state_is_read_only(self):
        self.assertIn("password", PaymentAdmin.exclude)
        for field in ("status", "paid_at", "organization", "failure_code", "amount"):
            self.assertIn(field, PaymentAdmin.readonly_fields)
