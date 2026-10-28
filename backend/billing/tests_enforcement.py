from datetime import timedelta
from decimal import Decimal
from unittest import mock

from django.core.cache import cache
from django.db import connection
from django.test import TransactionTestCase
from django.utils import timezone
from django_tenants.utils import tenant_context
from rest_framework.exceptions import ValidationError
from rest_framework.test import APIClient

from accounts.models import User
from organizations.models import Domain, Organization
from profiles.models import Profile
from roles.models import Role, UserRole
from students.models import Student

from .enforcement import check_student_capacity
from .models import Plan, Subscription
from .tasks import send_renewal_reminders


class EnforcementTests(TransactionTestCase):
    SCHEMA, DOMAIN = "enforce_school", "enforce.localhost"

    def setUp(self):
        cache.clear()
        connection.set_schema_to_public()
        self.school = Organization.objects.create(schema_name=self.SCHEMA, name="Enforce School",
                                                  email="office@enforce.test")
        Domain.objects.create(domain=self.DOMAIN, tenant=self.school, is_primary=True)
        self.plan = Plan.objects.create(code="en-plan", name="Small", monthly_price=Decimal("100.00"), student_limit=2)
        self.sub = Subscription.objects.create(organization=self.school, plan=self.plan, cycle="monthly",
                                               status=Subscription.ACTIVE,
                                               paid_until=timezone.now() + timedelta(days=10))
        self.owner = User.objects.create_user(username="en_owner", email="en_owner@en.test", password="Pass1234!")
        with tenant_context(self.school):
            role, _ = Role.objects.get_or_create(slug="owner", defaults={"name": "Owner", "is_system_role": True})
            UserRole.objects.create(user=self.owner, role=role)
        self.client = APIClient()
        assert self.client.post("/api/auth/login/", {"username": "en_owner", "password": "Pass1234!"},
                                HTTP_HOST=self.DOMAIN).status_code == 200

    def tearDown(self):
        connection.set_schema_to_public()
        Subscription.objects.filter(organization=self.school).delete()
        Plan.objects.filter(code="en-plan").delete()
        self.school.delete(force_drop=True)
        User.objects.filter(username="en_owner").delete()

    def _make_read_only(self):
        self.sub.status = Subscription.READ_ONLY
        self.sub.paid_until = timezone.now() - timedelta(days=20)
        self.sub.save()

    def _write(self):
        return self.client.post("/api/academics/programs/", {"name": "New Program", "code": "NP"},
                                format="json", HTTP_HOST=self.DOMAIN)

    def test_a_paid_school_can_make_changes(self):
        self.assertNotEqual(self._write().status_code, 402)

    def test_an_unpaid_school_can_read_but_not_change(self):
        self._make_read_only()
        response = self._write()
        self.assertEqual(response.status_code, 402)
        self.assertEqual(response.json()["code"], "subscription_read_only")
        self.assertEqual(self.client.get("/api/academics/programs/", HTTP_HOST=self.DOMAIN).status_code, 200)

    def test_an_unpaid_school_can_still_reach_billing_and_sign_out(self):
        self._make_read_only()
        self.assertNotEqual(self.client.post("/api/billing/my/pay/", {}, format="json", HTTP_HOST=self.DOMAIN).status_code, 402)
        self.assertNotEqual(self.client.post("/api/auth/logout/", HTTP_HOST=self.DOMAIN).status_code, 402)

    def test_grace_period_still_allows_changes(self):
        self.sub.status = Subscription.PAST_DUE
        self.sub.paid_until = timezone.now() - timedelta(days=2)
        self.sub.grace_ends_at = timezone.now() + timedelta(days=5)
        self.sub.save()
        self.assertNotEqual(self._write().status_code, 402)

    def test_legacy_schools_and_schools_without_billing_are_never_blocked(self):
        self._make_read_only()
        self.sub.is_legacy = True
        self.sub.save()
        self.assertNotEqual(self._write().status_code, 402)
        self.sub.delete()
        self.assertNotEqual(self._write().status_code, 402)

    def test_student_limit(self):
        with tenant_context(self.school):
            for i in range(2):
                Student.objects.create(profile=Profile.objects.create(first_name=f"S{i}", last_name="T"),
                                       enrollment_id=f"EN-{i}", status="active")
            with self.assertRaises(ValidationError) as raised:
                check_student_capacity()
            self.assertIn("allows 2 students", str(raised.exception.detail["error"]))
            Student.objects.filter(enrollment_id="EN-0").update(status="inactive")
            check_student_capacity()  # back under the limit

    def test_reminders_are_sent_once(self):
        self.sub.paid_until = timezone.now() + timedelta(days=7, hours=2)
        self.sub.save()
        with mock.patch("notifications.services.queue_email") as email:
            self.assertEqual(send_renewal_reminders(), 1)
            self.assertEqual(send_renewal_reminders(), 0)
        email.assert_called_once()
        with tenant_context(self.school):
            from notifications.models import Notification

            self.assertEqual(Notification.objects.filter(recipient_user_id=self.owner.id, category="billing").count(), 1)
