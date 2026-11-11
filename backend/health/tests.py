from django.contrib.auth import get_user_model
from django.test import TransactionTestCase
from django_tenants.utils import tenant_context

from fees.tests import FeesFixtureMixin

from .models import HealthIncident, StudentHealthProfile

User = get_user_model()


class HealthFixture(FeesFixtureMixin):
    SCHEMA_NAME = "health_test_school"
    DOMAIN = "healthtest.localhost"

    def setUp(self):
        super().setUp()
        self.nurse = User.objects.create_user(username="hl_nurse", email="n@healthtest.com", password="Pass1234!")
        self._give_role_only(self.nurse, ["manage_health_records"])
        self.teacher = User.objects.create_user(username="hl_teacher", email="t@healthtest.com", password="Pass1234!")
        self._give_role_only(self.teacher, ["view_health_records"])
        self.url = f"/api/health-records/students/{self.student1.id}/"

    def _save_profile(self, client, **data):
        return client.put(self.url, data, format="json", HTTP_HOST=self.DOMAIN)


class ProfileTests(HealthFixture, TransactionTestCase):
    def test_nurse_saves_and_teacher_reads(self):
        resp = self._save_profile(self._client_as(self.nurse), allergies="Peanuts (severe, carries EpiPen)")
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertTrue(resp.data["has_alert"])
        read = self._client_as(self.teacher).get(self.url, HTTP_HOST=self.DOMAIN)
        self.assertEqual(read.status_code, 200)
        self.assertEqual(read.data["profile"]["allergies"], "Peanuts (severe, carries EpiPen)")
        self.assertFalse(read.data["can_manage"])

    def test_a_student_without_a_profile_reads_as_empty(self):
        read = self._client_as(self.teacher).get(self.url, HTTP_HOST=self.DOMAIN)
        self.assertEqual(read.status_code, 200)
        self.assertEqual(read.data["profile"]["allergies"], "")
        with tenant_context(self.school):
            self.assertFalse(StudentHealthProfile.objects.exists())

    def test_teacher_cannot_edit(self):
        self.assertEqual(self._save_profile(self._client_as(self.teacher), allergies="x").status_code, 403)

    def test_other_staff_cannot_read(self):
        self.assertEqual(self._client_as(self.random_staff_user).get(self.url, HTTP_HOST=self.DOMAIN).status_code, 403)

    def test_parent_reads_own_child_only(self):
        self._save_profile(self._client_as(self.nurse), medical_conditions="Asthma")
        parent = self._client_as(self.parent1_user)
        self.assertEqual(parent.get(self.url, HTTP_HOST=self.DOMAIN).data["profile"]["medical_conditions"], "Asthma")
        other = f"/api/health-records/students/{self.student2.id}/"
        self.assertEqual(parent.get(other, HTTP_HOST=self.DOMAIN).status_code, 403)
        self.assertEqual(self._save_profile(parent, allergies="x").status_code, 403)

    def test_student_cannot_read_health_records(self):
        self.assertEqual(self._client_as(self.student1_user).get(self.url, HTTP_HOST=self.DOMAIN).status_code, 403)

    def test_audit_log_names_fields_but_not_their_contents(self):
        from core.models import AuditLog

        self._save_profile(self._client_as(self.nurse), allergies="Penicillin")
        with tenant_context(self.school):
            entry = AuditLog.objects.get(action="health_profile_updated")
            self.assertIn("allergies", str(entry.changes))
            self.assertNotIn("Penicillin", str(entry.changes))


class IncidentTests(HealthFixture, TransactionTestCase):
    def _record(self, client, **extra):
        data = {"occurred_at": "2026-11-10T10:30:00+05:30", "kind": "injury", "description": "Fell in the playground",
                "action_taken": "Cleaned and bandaged the knee", **extra}
        return client.post(f"{self.url}incidents/", data, format="json", HTTP_HOST=self.DOMAIN)

    def test_nurse_records_and_follows_up(self):
        nurse = self._client_as(self.nurse)
        resp = self._record(nurse)
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertFalse(resp.data["parent_informed"])
        patch = nurse.patch(f"/api/health-records/incidents/{resp.data['id']}/", {"parent_informed": True},
                            format="json", HTTP_HOST=self.DOMAIN)
        self.assertEqual(patch.status_code, 200)
        self.assertTrue(patch.data["parent_informed"])
        parent = self._client_as(self.parent1_user).get(self.url, HTTP_HOST=self.DOMAIN)
        self.assertEqual(parent.data["incidents"][0]["description"], "Fell in the playground")

    def test_empty_description_is_refused(self):
        self.assertEqual(self._record(self._client_as(self.nurse), description="   ").status_code, 400)

    def test_teacher_cannot_record(self):
        self.assertEqual(self._record(self._client_as(self.teacher)).status_code, 403)

    def test_incident_cannot_be_deleted(self):
        resp = self._record(self._client_as(self.nurse))
        gone = self._client_as(self.nurse).delete(f"/api/health-records/incidents/{resp.data['id']}/", HTTP_HOST=self.DOMAIN)
        self.assertEqual(gone.status_code, 405)
        with tenant_context(self.school):
            self.assertEqual(HealthIncident.objects.count(), 1)

    def test_log_filters_by_date(self):
        nurse = self._client_as(self.nurse)
        self._record(nurse)
        self._record(nurse, occurred_at="2026-10-01T09:00:00+05:30")
        log = self._client_as(self.teacher).get("/api/health-records/incidents/?from=2026-11-01", HTTP_HOST=self.DOMAIN)
        self.assertEqual(log.status_code, 200)
        self.assertEqual(log.data["count"], 1)
        bad = self._client_as(self.teacher).get("/api/health-records/incidents/?from=yesterday", HTTP_HOST=self.DOMAIN)
        self.assertEqual(bad.status_code, 400)


class AlertTests(HealthFixture, TransactionTestCase):
    def test_alerts_list_only_students_with_something_to_know(self):
        nurse = self._client_as(self.nurse)
        self._save_profile(nurse, allergies="Bee stings")
        nurse.put(f"/api/health-records/students/{self.student2.id}/", {"doctor_name": "Dr Rao"},
                  format="json", HTTP_HOST=self.DOMAIN)
        resp = self._client_as(self.teacher).get(f"/api/health-records/alerts/?section={self.section_a.id}", HTTP_HOST=self.DOMAIN)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual([r["student"] for r in resp.data], [str(self.student1.id)])

    def test_alerts_need_the_permission(self):
        self.assertEqual(self._client_as(self.parent1_user).get("/api/health-records/alerts/", HTTP_HOST=self.DOMAIN).status_code, 403)
