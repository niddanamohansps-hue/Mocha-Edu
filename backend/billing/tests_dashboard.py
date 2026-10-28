from datetime import timedelta
from decimal import Decimal

from django.db import connection
from django.test import Client, TransactionTestCase
from django.utils import timezone

from accounts.models import User
from organizations.models import Domain, Organization

from .admin_dashboard import monthly_value, summary
from .models import Invoice, Plan, Subscription

URL = "/admin/billing/dashboard/"


class DashboardTests(TransactionTestCase):
    def setUp(self):
        connection.set_schema_to_public()
        public, _ = Organization.objects.get_or_create(schema_name="public", defaults={"name": "Public Schema"})
        Domain.objects.get_or_create(domain="testserver", tenant=public, defaults={"is_primary": True})
        Organization.auto_create_schema = False  # billing rows only; no school schemas needed
        self.addCleanup(setattr, Organization, "auto_create_schema", True)
        self.plan = Plan.objects.create(code="db-plan", name="Dash Plan", monthly_price=Decimal("1000.00"),
                                        yearly_price=Decimal("12000.00"), trial_days=14)
        now = timezone.now()
        self.schools = {}
        for name, cycle, status, paid_until in (
            ("Monthly School", "monthly", Subscription.ACTIVE, now + timedelta(days=10)),
            ("Yearly School", "yearly", Subscription.ACTIVE, now + timedelta(days=200)),
            ("Late School", "monthly", Subscription.READ_ONLY, now - timedelta(days=20)),
            ("Trial School", "monthly", Subscription.TRIAL, None),
        ):
            org = Organization.objects.create(schema_name=name.lower().replace(" ", "_"), name=name, email=f"{cycle}@x.test")
            self.schools[name] = Subscription.objects.create(
                organization=org, plan=self.plan, cycle=cycle, status=status, paid_until=paid_until,
                trial_ends_at=now + timedelta(days=3) if status == Subscription.TRIAL else None)
        self.admin = User.objects.create_superuser(username="dash_admin", email="dash@x.test", password="Pass1234!")
        self.staff = User.objects.create_user(username="dash_staff", email="staff@x.test", password="Pass1234!", is_staff=True)

    def tearDown(self):
        Invoice.objects.all().delete()
        Subscription.objects.filter(plan=self.plan).delete()
        Organization.objects.filter(name__in=list(self.schools)).delete()
        Plan.objects.filter(code="db-plan").delete()
        User.objects.filter(username__in=["dash_admin", "dash_staff"]).delete()

    def _client(self, user):
        client = Client()
        client.force_login(user)
        return client

    def test_only_superusers_see_it(self):
        self.assertEqual(Client().get(URL).status_code, 302)  # to the admin login
        self.assertEqual(self._client(self.staff).get(URL).status_code, 403)
        response = self._client(self.admin).get(URL)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Late School")
        self.assertContains(response, "Monthly recurring revenue")

    def test_mrr_counts_paying_monthly_and_yearly_only(self):
        data = summary()
        self.assertEqual(data["mrr"], Decimal("2000.00"))  # 1000 monthly + 12000 / 12; trial and read-only add nothing
        self.assertEqual(monthly_value(self.schools["Trial School"]), Decimal("0.00"))
        self.assertEqual(data["counts"]["read_only"], 1)
        self.assertEqual([r["sub"].organization.name for r in data["overdue"]], ["Late School"])
        self.assertEqual([r["sub"].organization.name for r in data["trials_ending"]], ["Trial School"])

    def test_extend_trial(self):
        trial = self.schools["Trial School"]
        before = trial.trial_ends_at
        response = self._client(self.admin).post(URL, {"subscription": trial.pk, "action": "extend_trial", "days": 10})
        self.assertEqual(response.status_code, 302)
        trial.refresh_from_db()
        self.assertEqual((trial.trial_ends_at - before).days, 10)

    def test_change_plan_only_to_an_offered_cycle(self):
        other = Plan.objects.create(code="db-plan2", name="Other", monthly_price=Decimal("500.00"))
        try:
            school = self.schools["Monthly School"]
            self._client(self.admin).post(URL, {"subscription": school.pk, "action": "change_plan", "plan": other.pk, "cycle": "yearly"})
            school.refresh_from_db()
            self.assertEqual(school.plan, self.plan)  # Other has no yearly price: refused
            self._client(self.admin).post(URL, {"subscription": school.pk, "action": "change_plan", "plan": other.pk, "cycle": "monthly"})
            school.refresh_from_db()
            self.assertEqual(school.plan, other)
        finally:
            Subscription.objects.filter(plan__code="db-plan2").update(plan=self.plan)
            other.delete()

    def test_mark_legacy_gives_full_access(self):
        late = self.schools["Late School"]
        self._client(self.admin).post(URL, {"subscription": late.pk, "action": "mark_legacy"})
        late.refresh_from_db()
        self.assertTrue(late.is_legacy)
        self.assertTrue(late.can_write())

    def test_staff_cannot_change_anything(self):
        trial = self.schools["Trial School"]
        before = trial.trial_ends_at
        self.assertEqual(self._client(self.staff).post(URL, {"subscription": trial.pk, "action": "extend_trial", "days": 30}).status_code, 403)
        trial.refresh_from_db()
        self.assertEqual(trial.trial_ends_at, before)
