"""Audit fixes F-2 to F-4: a teacher's schedule access follows their exact subject-and-section pairs.

F-2  listing schedules shows only the pairs they teach (not every subject of every section they teach in);
F-3  editing a schedule cannot move it to a pair they do not teach;
F-4  locking a schedule needs the same access as entering its marks.

Creates tenant schemas, so it needs a disposable PostgreSQL database.
"""
import datetime

from django.test import TransactionTestCase
from django_tenants.utils import tenant_context

from academics.models import SubjectAssignment
from roles.models import Permission, Role

from .tests import ExamFixtureMixin

SCHEDULES = "/api/examinations/schedules/"


class ScheduleScopeTests(ExamFixtureMixin, TransactionTestCase):
    def setUp(self):
        super().setUp()
        # The teacher teaches Maths in A and Science in B, but not Science in A nor Maths in B.
        with tenant_context(self.school):
            SubjectAssignment.objects.create(section=self.section_b, subject=self.second_subject, instructor=self.instructor)
        self.maths_a = self._create_schedule(section=self.section_a, subject=self.subject)
        self.science_b = self._create_schedule(section=self.section_b, subject=self.second_subject, date=datetime.date(2026, 6, 3))
        # Taught by somebody else: Science in A and Maths in B.
        with tenant_context(self.school):
            SubjectAssignment.objects.create(section=self.section_a, subject=self.second_subject, instructor=self.other_instructor)
            SubjectAssignment.objects.create(section=self.section_b, subject=self.subject, instructor=self.other_instructor)
        self.science_a = self._create_schedule(section=self.section_a, subject=self.second_subject, date=datetime.date(2026, 6, 4))
        self.maths_b = self._create_schedule(section=self.section_b, subject=self.subject, date=datetime.date(2026, 6, 5))
        self.client = self._client_as(self.instructor_user)

    def ids(self, response):
        data = response.data
        return {r["id"] for r in (data["results"] if isinstance(data, dict) and "results" in data else data)}

    def test_f2_the_list_shows_only_the_pairs_the_teacher_teaches(self):
        resp = self.client.get(SCHEDULES, HTTP_HOST=self.DOMAIN)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(self.ids(resp), {str(self.maths_a.id), str(self.science_b.id)})
        self.assertEqual(self.client.get(f"{SCHEDULES}{self.science_a.id}/", HTTP_HOST=self.DOMAIN).status_code, 404)

    def test_f2_the_owner_still_sees_every_schedule(self):
        owner = self._client_as(self.owner_user)
        self.assertEqual(len(self.ids(owner.get(SCHEDULES, HTTP_HOST=self.DOMAIN))), 4)

    def test_f3_a_teacher_cannot_move_a_schedule_to_a_pair_they_do_not_teach(self):
        with tenant_context(self.school):
            self.maths_b.delete()  # so the move is refused for the teacher's scope, not as a duplicate schedule
        resp = self.client.patch(f"{SCHEDULES}{self.maths_a.id}/", {"section": str(self.section_b.id)}, format="json", HTTP_HOST=self.DOMAIN)
        self.assertEqual(resp.status_code, 403, resp.data)
        with tenant_context(self.school):
            self.maths_a.refresh_from_db()
            self.assertEqual(self.maths_a.section_id, self.section_a.id)

    def test_f3_editing_within_their_own_pair_still_works(self):
        resp = self.client.patch(f"{SCHEDULES}{self.maths_a.id}/", {"max_marks": "80", "pass_marks": "30"}, format="json", HTTP_HOST=self.DOMAIN)
        self.assertEqual(resp.status_code, 200, resp.data)

    def test_f4_locking_needs_access_to_that_schedule(self):
        with tenant_context(self.school):
            role = Role.objects.get(slug="instructor")
            role.permissions.add(Permission.objects.get(codename="manage_marks"))
        mine = self.client.post(f"{SCHEDULES}{self.maths_a.id}/lock/", {"is_locked": True}, format="json", HTTP_HOST=self.DOMAIN)
        self.assertEqual(mine.status_code, 200, mine.data)
        theirs = self.client.post(f"{SCHEDULES}{self.science_a.id}/lock/", {"is_locked": True}, format="json", HTTP_HOST=self.DOMAIN)
        self.assertIn(theirs.status_code, (403, 404))
        with tenant_context(self.school):
            self.science_a.refresh_from_db()
            self.assertFalse(self.science_a.is_locked)
