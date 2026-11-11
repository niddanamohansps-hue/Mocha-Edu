from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TransactionTestCase
from django_tenants.utils import tenant_context

from fees.models import FeeStructure, StudentFee
from fees.tests import FeesFixtureMixin
from profiles.models import Profile

from .models import Hostel, HostelAllocation, HostelRoom

User = get_user_model()


class HostelFixture(FeesFixtureMixin):
    SCHEMA_NAME = "hostel_test_school"
    DOMAIN = "hosteltest.localhost"

    def setUp(self):
        super().setUp()
        with tenant_context(self.school):
            Profile.objects.filter(id=self.student1.profile_id).update(gender="male")
            Profile.objects.filter(id=self.student2.profile_id).update(gender="female")
            self.boys = Hostel.objects.create(name="Tagore House", gender="boys")
            self.room = HostelRoom.objects.create(hostel=self.boys, number="101", capacity=1)
            self.room2 = HostelRoom.objects.create(hostel=self.boys, number="102", capacity=2)
        self.warden = User.objects.create_user(username="ho_warden", email="w@hosteltest.com", password="Pass1234!")
        self._give_role_only(self.warden, ["view_hostel", "manage_hostel", "manage_fee_structures"])
        self.viewer = User.objects.create_user(username="ho_viewer", email="v@hosteltest.com", password="Pass1234!")
        self._give_role_only(self.viewer, ["view_hostel"])

    def _allocate(self, client, student, room, **extra):
        return client.post("/api/hostel/allocations/", {"student": str(student.id), "room": str(room.id), **extra},
                           format="json", HTTP_HOST=self.DOMAIN)


class AllocationTests(HostelFixture, TransactionTestCase):
    def test_allocate_and_see_it(self):
        resp = self._allocate(self._client_as(self.warden), self.student1, self.room)
        self.assertEqual(resp.status_code, 201, resp.data)
        rooms = self._client_as(self.viewer).get(f"/api/hostel/rooms/?hostel={self.boys.id}", HTTP_HOST=self.DOMAIN)
        rows = rooms.data["results"] if isinstance(rooms.data, dict) else rooms.data
        row = next(r for r in rows if r["number"] == "101")
        self.assertEqual(row["occupied"], 1)
        self.assertEqual(row["occupants"][0]["student"], str(self.student1.id))

    def test_a_full_room_is_refused(self):
        warden = self._client_as(self.warden)
        self._allocate(warden, self.student1, self.room)
        with tenant_context(self.school):
            Profile.objects.filter(id=self.student2.profile_id).update(gender="male")
        resp = self._allocate(warden, self.student2, self.room)
        self.assertEqual(resp.status_code, 400)
        self.assertIn("full", str(resp.data))

    def test_gender_rule(self):
        resp = self._allocate(self._client_as(self.warden), self.student2, self.room2)
        self.assertEqual(resp.status_code, 400)
        self.assertIn("boys hostel", str(resp.data))

    def test_moving_closes_the_old_stay(self):
        warden = self._client_as(self.warden)
        self._allocate(warden, self.student1, self.room, start_date="2026-04-01")
        resp = self._allocate(warden, self.student1, self.room2, start_date="2026-07-01")
        self.assertEqual(resp.status_code, 201, resp.data)
        with tenant_context(self.school):
            stays = list(HostelAllocation.objects.filter(student=self.student1).order_by("start_date"))
            self.assertEqual(str(stays[0].end_date), "2026-06-30")
            self.assertIsNone(stays[1].end_date)

    def test_same_day_move_is_a_correction(self):
        warden = self._client_as(self.warden)
        self._allocate(warden, self.student1, self.room, start_date="2026-07-01")
        resp = self._allocate(warden, self.student1, self.room2, start_date="2026-07-01")
        self.assertEqual(resp.status_code, 201, resp.data)
        early = self._allocate(warden, self.student1, self.room, start_date="2026-06-01")
        self.assertEqual(early.status_code, 400)

    def test_vacate(self):
        warden = self._client_as(self.warden)
        a = self._allocate(warden, self.student1, self.room, start_date="2026-04-01").data
        resp = warden.post(f"/api/hostel/allocations/{a['id']}/vacate/", {"end_date": "2026-10-31"}, format="json", HTTP_HOST=self.DOMAIN)
        self.assertEqual(resp.status_code, 200)
        again = warden.post(f"/api/hostel/allocations/{a['id']}/vacate/", {}, format="json", HTTP_HOST=self.DOMAIN)
        self.assertEqual(again.status_code, 400)

    def test_capacity_cannot_drop_below_occupants(self):
        warden = self._client_as(self.warden)
        self._allocate(warden, self.student1, self.room2)
        resp = warden.patch(f"/api/hostel/rooms/{self.room2.id}/", {"capacity": 0}, format="json", HTTP_HOST=self.DOMAIN)
        self.assertEqual(resp.status_code, 400)

    def test_viewer_cannot_allocate(self):
        self.assertEqual(self._allocate(self._client_as(self.viewer), self.student1, self.room).status_code, 403)

    def test_parent_sees_own_child_only(self):
        self._allocate(self._client_as(self.warden), self.student1, self.room)
        parent = self._client_as(self.parent1_user)
        mine = parent.get(f"/api/hostel/students/{self.student1.id}/", HTTP_HOST=self.DOMAIN)
        self.assertEqual(mine.status_code, 200)
        self.assertEqual(mine.data["current"]["room_number"], "101")
        other = parent.get(f"/api/hostel/students/{self.student2.id}/", HTTP_HOST=self.DOMAIN)
        self.assertEqual(other.status_code, 403)


class HostelFeeTests(HostelFixture, TransactionTestCase):
    def test_charge_only_boarders(self):
        with tenant_context(self.school):
            fee = FeeStructure.objects.create(fee_head=self.fee_head, academic_year="2026", amount=Decimal("60000"))
            self.boys.fee_structure = fee
            self.boys.save(update_fields=["fee_structure"])
        warden = self._client_as(self.warden)
        self._allocate(warden, self.student1, self.room)
        warden.put(f"/api/fees/structures/{fee.id}/installments/", {"installments": [
            {"name": "Term 1", "percent": "50", "due_date": "2026-04-10"},
            {"name": "Term 2", "percent": "50", "due_date": "2026-10-10"},
        ]}, format="json", HTTP_HOST=self.DOMAIN)
        preview = warden.get(f"/api/hostel/hostels/{self.boys.id}/charge/", HTTP_HOST=self.DOMAIN)
        self.assertEqual(preview.status_code, 200, preview.data)
        self.assertEqual(preview.data["students_total"], 1)
        resp = warden.post(f"/api/hostel/hostels/{self.boys.id}/charge/", HTTP_HOST=self.DOMAIN)
        self.assertEqual(resp.status_code, 201)
        with tenant_context(self.school):
            self.assertEqual(StudentFee.objects.filter(student=self.student1, fee_structure=fee).count(), 2)
            self.assertFalse(StudentFee.objects.filter(student=self.student2, fee_structure=fee).exists())
        again = warden.post(f"/api/hostel/hostels/{self.boys.id}/charge/", HTTP_HOST=self.DOMAIN)
        self.assertEqual(again.data["fees_to_create"], 0)

    def test_charge_needs_a_fee_structure(self):
        resp = self._client_as(self.warden).post(f"/api/hostel/hostels/{self.boys.id}/charge/", HTTP_HOST=self.DOMAIN)
        self.assertEqual(resp.status_code, 400)

    def test_hostel_list_counts_beds(self):
        self._allocate(self._client_as(self.warden), self.student1, self.room2)
        resp = self._client_as(self.viewer).get("/api/hostel/hostels/", HTTP_HOST=self.DOMAIN)
        h = resp.data[0]
        self.assertEqual((h["rooms"], h["beds"], h["occupied"]), (2, 3, 1))
