"""Exam rooms and invigilators: sittings, seat allocation, duty allocation and their access rules."""
import datetime
import uuid
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TransactionTestCase
from django_tenants.utils import tenant_context
from rest_framework.test import APIRequestFactory, force_authenticate

from academics.models import AcademicLevel, Program, Section, Subject
from notifications.models import AlertLog, Notification
from organizations.models import Domain, Organization
from profiles.models import Profile
from roles.models import Role, UserRole
from roles.signals import seed_default_roles
from staff.models import Instructor, LeaveApplication, LeaveType, StaffMember
from students.models import Student, StudentLevel
from timetable.models import Period, Room, TimetableEntry

from . import allocation
from .allocation import AllocationError
from .allocation_views import DutyRosterView, ExamInvigilationViewSet, ExamSittingViewSet, MyDutiesView
from .views import ExaminationViewSet  # noqa: F401  (used by the date sheet tests)
from .models import ExamInvigilation, ExamSchedule, ExamSeat, ExamSitting, Examination, ExamType

User = get_user_model()
DAY1 = datetime.date(2026, 6, 2)
DAY2 = datetime.date(2026, 6, 3)
NINE = datetime.time(9, 0)
NOON = datetime.time(12, 0)


class AllocationBase(TransactionTestCase):
    def setUp(self):
        suffix = uuid.uuid4().hex[:8]
        connection.set_schema_to_public()
        self.school = Organization.objects.create(schema_name=f"alloc_{suffix}", name="Allocation Test School")
        Domain.objects.create(domain=f"alloc-{suffix}.localhost", tenant=self.school, is_primary=True)
        self.factory = APIRequestFactory()
        with tenant_context(self.school):
            seed_default_roles()
            program = Program.objects.create(name="High School", code="HSAL")
            level = AcademicLevel.objects.create(program=program, name="Grade 10", order=1)
            self.section_a = Section.objects.create(level=level, name="A", capacity=40)
            self.section_b = Section.objects.create(level=level, name="B", capacity=40)
            self.math = Subject.objects.create(level=level, name="Math", code="MTHAL")
            self.english = Subject.objects.create(level=level, name="English", code="ENGAL")
            self.exam_type = ExamType.objects.create(name="Term", order=1)
            self.exam = Examination.objects.create(
                academic_year="2026", name="Term 1", exam_type=self.exam_type,
                start_date=DAY1, end_date=DAY2,
            )
            # Sitting 1: Math for A and English for B at the same time. Sitting 2: Math for B the next day.
            self.paper_a = self._paper(self.math, self.section_a, DAY1)
            self.paper_b = self._paper(self.english, self.section_b, DAY1)
            self.paper_b2 = self._paper(self.math, self.section_b, DAY2)
            self.students_a = [self._student(f"A{i}", self.section_a, level) for i in range(1, 5)]
            self.students_b = [self._student(f"B{i}", self.section_b, level) for i in range(1, 4)]
            self.room_small = Room.objects.create(name="R1", capacity=4)
            self.room_small2 = Room.objects.create(name="R2", capacity=4)
            self.room_big = Room.objects.create(name="Hall", capacity=10)

            self.teachers = [self._teacher(f"T{i}") for i in range(1, 7)]  # employee ids T1..T6
            period = Period.objects.create(academic_year="2026", name="P1", order=1,
                                           start_time=datetime.time(8, 0), end_time=datetime.time(8, 45))
            # T1 teaches class A and T2 teaches class B, so the own-class rule has something to bite on.
            for teacher, section in ((self.teachers[0], self.section_a), (self.teachers[1], self.section_b)):
                TimetableEntry.objects.create(
                    academic_year="2026", section=section, subject=self.math, instructor=teacher.instructor_record,
                    day_of_week=0, period=period,
                )
            self.owner = self._user("owner", "owner")
            self.clerk = self._user("staff", "clerk")
            self.sitting1, self.sitting2 = allocation.sync_sittings(self.exam)

    def _paper(self, subject, section, date, start=NINE, end=NOON, exam=None):
        return ExamSchedule.objects.create(
            examination=exam or self.exam, academic_year="2026", subject=subject, section=section,
            date=date, start_time=start, end_time=end, max_marks=Decimal("100"), pass_marks=Decimal("35"),
        )

    def _student(self, code, section, level):
        student = Student.objects.create(
            profile=Profile.objects.create(first_name=code, last_name="Pupil"), enrollment_id=f"ENR-{code}", status="active"
        )
        StudentLevel.objects.create(student=student, level=level, section=section, academic_year="2026", is_current=True)
        return student

    def _teacher(self, code, login=False):
        user = None
        if login:
            user = User.objects.create_user(username=f"{code.lower()}_{uuid.uuid4().hex[:5]}@s.com", password="Password123!")
        profile = Profile.objects.create(user_id=user.id if user else None, first_name=code, last_name="Teacher")
        member = StaffMember.objects.create(profile=profile, employee_id=code, designation="Teacher")
        Instructor.objects.create(staff_member=member, specialization="General")
        member.login_user = user
        return member

    def _user(self, role_slug, label):
        user = User.objects.create_user(
            username=f"{label}_{uuid.uuid4().hex[:6]}@s.com", email=f"{label}@s.com", password="Password123!"
        )
        Profile.objects.create(user_id=user.id, first_name=label.title(), last_name="User")
        UserRole.objects.create(user=user, role=Role.objects.get(slug=role_slug))
        return user

    def _leave(self, member, day, status="approved"):
        leave_type, _ = LeaveType.objects.get_or_create(code="CL", defaults={"name": "Casual"})
        return LeaveApplication.objects.create(
            staff=member, leave_type=leave_type, academic_year="2026", start_date=day, end_date=day,
            reason="x", status=status,
        )

    def _call(self, viewset, mapping, method, user, data=None, **kwargs):
        request = (self.factory.get("/x/", data) if method == "get" else getattr(self.factory, method)("/x/", data, format="json"))
        request.tenant = self.school
        force_authenticate(request, user=user)
        return viewset.as_view(mapping)(request, **kwargs)

    def _rooms_for_two(self):
        return [self.room_small.id, self.room_small2.id]


class SittingTests(AllocationBase):
    def test_sittings_group_papers_by_date_and_start_and_follow_schedule_changes(self):
        with tenant_context(self.school):
            self.assertEqual([(s.date, s.start_time) for s in (self.sitting1, self.sitting2)], [(DAY1, NINE), (DAY2, NINE)])
            self.assertEqual(len(allocation.sitting_schedules(self.sitting1)), 2)
            # A later end time stretches the sitting; running sync again changes nothing else.
            self.paper_a.end_time = datetime.time(13, 0)
            self.paper_a.save()
            sittings = allocation.sync_sittings(self.exam)
            self.assertEqual(len(sittings), 2)
            self.assertEqual(sittings[0].end_time, datetime.time(13, 0))
            self.assertEqual(ExamSitting.objects.count(), 2)
            # A sitting whose papers are all gone disappears with its allocations.
            allocation.allocate_rooms(self.sitting2)
            self.paper_b2.delete()
            self.assertEqual(len(allocation.sync_sittings(self.exam)), 1)
            self.assertEqual(ExamSeat.objects.filter(sitting__date=DAY2).count(), 0)


class RoomAllocationTests(AllocationBase):
    def test_papers_are_interleaved_so_neighbours_sit_different_papers(self):
        with tenant_context(self.school):
            result = allocation.allocate_rooms(self.sitting1)  # the biggest room (Hall, 10 seats) holds all seven
            self.assertEqual((result["students"], result["rooms"]), (7, 1))
            seats = list(ExamSeat.objects.filter(sitting=self.sitting1).order_by("seat_number"))
            self.assertEqual([s.seat_number for s in seats], list(range(1, 8)))
            papers = [s.schedule_id for s in seats]
            # Four from A and three from B alternate: A B A B A B A.
            self.assertTrue(all(papers[i] != papers[i + 1] for i in range(6)))

    def test_without_mixing_each_paper_stays_together(self):
        with tenant_context(self.school):
            allocation.allocate_rooms(self.sitting1, mix=False)
            papers = [s.schedule_id for s in ExamSeat.objects.filter(sitting=self.sitting1).order_by("seat_number")]
            self.assertEqual(sum(papers[i] != papers[i + 1] for i in range(6)), 1)  # a single change of paper

    def test_students_spill_into_more_rooms_and_every_seat_is_unique(self):
        with tenant_context(self.school):
            result = allocation.allocate_rooms(self.sitting1, room_ids=self._rooms_for_two())
            self.assertEqual(result["rooms"], 2)
            counts = sorted(ExamSeat.objects.filter(sitting=self.sitting1).values_list("room__name").order_by("room__name"))
            self.assertEqual(len(counts), 7)
            positions = ExamSeat.objects.filter(sitting=self.sitting1).values_list("room_id", "seat_number")
            self.assertEqual(len(set(positions)), 7)
            self.assertEqual(ExamSeat.objects.filter(sitting=self.sitting1, room=self.room_small).count(), 4)

    def test_too_few_seats_changes_nothing(self):
        with tenant_context(self.school):
            allocation.allocate_rooms(self.sitting1)
            before = sorted(ExamSeat.objects.filter(sitting=self.sitting1).values_list("student_id", "room_id", "seat_number"))
            with self.assertRaises(AllocationError) as caught:
                allocation.allocate_rooms(self.sitting1, room_ids=[self.room_small.id])  # 4 seats for 7 students
            self.assertIn("short by 3", str(caught.exception))
            after = sorted(ExamSeat.objects.filter(sitting=self.sitting1).values_list("student_id", "room_id", "seat_number"))
            self.assertEqual(before, after)

    def test_a_room_in_use_at_an_overlapping_time_is_not_offered(self):
        with tenant_context(self.school):
            allocation.allocate_rooms(self.sitting1)  # takes the Hall for 09:00-12:00
            other = Examination.objects.create(
                academic_year="2026", name="Unit test", exam_type=self.exam_type, start_date=DAY1, end_date=DAY1
            )
            self._paper(self.math, self.section_a, DAY1, start=datetime.time(10, 0), end=datetime.time(11, 0), exam=other)
            clash = allocation.sync_sittings(other)[0]
            allocation.allocate_rooms(clash)  # four students, and the Hall is taken
            used = set(ExamSeat.objects.filter(sitting=clash).values_list("room__name", flat=True))
            self.assertNotIn("Hall", used)
            with self.assertRaises(AllocationError):
                allocation.allocate_rooms(clash, room_ids=[self.room_big.id])

    def test_a_student_in_two_papers_at_once_is_reported(self):
        with tenant_context(self.school):
            self._paper(self.english, self.section_a, DAY1)  # class A now has two papers at 09:00
            with self.assertRaises(AllocationError) as caught:
                allocation.allocate_rooms(self.sitting1)
            self.assertIn("two papers", str(caught.exception))

    def test_moving_a_student_into_an_occupied_seat_swaps_them(self):
        with tenant_context(self.school):
            allocation.allocate_rooms(self.sitting1)
            first, second = (ExamSeat.objects.get(sitting=self.sitting1, seat_number=n) for n in (1, 2))
            allocation.move_seat(self.sitting1, first.student_id, self.room_big.id, 2)
            first.refresh_from_db()
            second.refresh_from_db()
            self.assertEqual((first.seat_number, second.seat_number), (2, 1))
            allocation.move_seat(self.sitting1, first.student_id, self.room_big.id, 9)  # a free seat
            first.refresh_from_db()
            self.assertEqual(first.seat_number, 9)
            for bad in (0, 11):
                with self.assertRaises(AllocationError):
                    allocation.move_seat(self.sitting1, first.student_id, self.room_big.id, bad)

    def test_the_plan_lists_rooms_and_flags_students_enrolled_after_allocation(self):
        with tenant_context(self.school):
            allocation.allocate_rooms(self.sitting1)
            self._student("A9", self.section_a, self.section_a.level)
            plan = allocation.build_sitting_plan(self.sitting1)
            self.assertEqual(plan["unseated"], 1)
            self.assertEqual(len(plan["rooms"]), 1)
            self.assertEqual(plan["rooms"][0]["room"]["name"], "Hall")
            self.assertEqual(len(plan["rooms"][0]["seats"]), 7)


class InvigilatorAllocationTests(AllocationBase):
    def _seat_two_rooms(self):
        allocation.allocate_rooms(self.sitting1, room_ids=self._rooms_for_two())

    def _on_duty(self, sitting=None):
        qs = ExamInvigilation.objects.filter(sitting=sitting or self.sitting1)
        return {i.staff.employee_id for i in qs}

    def test_rooms_must_be_allocated_first(self):
        with tenant_context(self.school):
            with self.assertRaises(AllocationError):
                allocation.allocate_invigilators(self.sitting1)

    def test_each_room_gets_a_chief_and_nobody_teaches_the_class_they_watch(self):
        with tenant_context(self.school):
            self._seat_two_rooms()
            allocation.allocate_invigilators(self.sitting1, per_room=2)
            duties = ExamInvigilation.objects.filter(sitting=self.sitting1)
            self.assertEqual(duties.count(), 4)
            for room in (self.room_small, self.room_small2):
                roles = sorted(duties.filter(room=room).values_list("role", flat=True))
                self.assertEqual(roles, ["chief", "invigilator"])
            # Both rooms hold classes A and B, so T1 (teaches A) and T2 (teaches B) are never picked.
            self.assertEqual(self._on_duty(), {"T3", "T4", "T5", "T6"})

    def test_the_own_class_rule_can_be_switched_off(self):
        with tenant_context(self.school):
            self._seat_two_rooms()
            allocation.allocate_invigilators(self.sitting1, per_room=2, avoid_own_class=False)
            self.assertEqual(self._on_duty(), {"T1", "T2", "T3", "T4"})  # simply the first four by employee id

    def test_staff_on_approved_leave_are_skipped_but_pending_leave_is_not(self):
        with tenant_context(self.school):
            self._seat_two_rooms()
            self._leave(self.teachers[2], DAY1, status="approved")  # T3
            self._leave(self.teachers[3], DAY1, status="pending")  # T4
            allocation.allocate_invigilators(self.sitting1, per_room=2, avoid_own_class=False)
            self.assertNotIn("T3", self._on_duty())
            self.assertIn("T4", self._on_duty())

    def test_too_few_staff_changes_nothing(self):
        with tenant_context(self.school):
            self._seat_two_rooms()
            allocation.allocate_invigilators(self.sitting1, per_room=2)
            before = self._on_duty()
            for teacher in self.teachers[2:4]:
                self._leave(teacher, DAY1)  # leaves only two free (T5, T6) besides the two class teachers
            with self.assertRaises(AllocationError) as caught:
                allocation.allocate_invigilators(self.sitting1, per_room=2)
            self.assertIn("Not enough available staff", str(caught.exception))
            self.assertEqual(self._on_duty(), before)

    def test_staff_already_on_duty_at_an_overlapping_time_are_skipped(self):
        with tenant_context(self.school):
            self._seat_two_rooms()
            other = Examination.objects.create(
                academic_year="2026", name="Unit test", exam_type=self.exam_type, start_date=DAY1, end_date=DAY1
            )
            self._paper(self.math, self.section_a, DAY1, start=datetime.time(10, 0), end=datetime.time(11, 0), exam=other)
            clash = allocation.sync_sittings(other)[0]
            ExamSeat.objects.create(sitting=clash, room=self.room_big, student=self.students_a[0],
                                    schedule=ExamSchedule.objects.get(examination=other), seat_number=1)
            ExamInvigilation.objects.create(sitting=clash, room=self.room_big, staff=self.teachers[2])  # T3 busy
            allocation.allocate_invigilators(self.sitting1, per_room=2, avoid_own_class=False)
            self.assertNotIn("T3", self._on_duty())

    def test_duties_are_spread_across_sittings(self):
        with tenant_context(self.school):
            self._seat_two_rooms()
            allocation.allocate_invigilators(self.sitting1, per_room=2)  # T3..T6, one duty each
            allocation.allocate_rooms(self.sitting2)  # class B only
            allocation.allocate_invigilators(self.sitting2, per_room=1)
            # T1 has no duty so far and does not teach class B; T2 teaches B. The fewest-duties rule picks T1.
            self.assertEqual(self._on_duty(self.sitting2), {"T1"})

    def test_reallocating_rooms_drops_duties_in_rooms_no_longer_used(self):
        with tenant_context(self.school):
            self._seat_two_rooms()
            allocation.allocate_invigilators(self.sitting1, per_room=2)
            result = allocation.allocate_rooms(self.sitting1)  # now everyone fits in the Hall
            self.assertEqual(result["duties_dropped"], 4)
            self.assertEqual(ExamInvigilation.objects.filter(sitting=self.sitting1).count(), 0)

    def test_replacing_an_invigilator_checks_the_replacement_is_free(self):
        with tenant_context(self.school):
            self._seat_two_rooms()
            allocation.allocate_invigilators(self.sitting1, per_room=2)
            duty = ExamInvigilation.objects.filter(sitting=self.sitting1).first()
            on_leave = self._leave(self.teachers[0], DAY1).staff  # T1
            with self.assertRaises(AllocationError):
                allocation.replace_invigilator(duty, on_leave)
            with self.assertRaises(AllocationError):  # already on this sitting
                allocation.replace_invigilator(duty, ExamInvigilation.objects.filter(sitting=self.sitting1).exclude(pk=duty.pk).first().staff)
            allocation.replace_invigilator(duty, self.teachers[1])  # T2 is free
            duty.refresh_from_db()
            self.assertEqual(duty.staff.employee_id, "T2")


class AllocationApiTests(AllocationBase):
    def test_only_users_with_the_permission_can_allocate_and_staff_see_their_own_duties(self):
        with tenant_context(self.school):
            denied = self._call(ExamSittingViewSet, {"post": "allocate_rooms"}, "post", self.clerk, {}, pk=str(self.sitting1.pk))
            self.assertEqual(denied.status_code, 403)
            self.assertEqual(self._call(ExamSittingViewSet, {"get": "list"}, "get", self.clerk,
                                        {"examination": str(self.exam.pk)}).status_code, 403)

            ok = self._call(ExamSittingViewSet, {"post": "allocate_rooms"}, "post", self.owner,
                            {"rooms": [str(i) for i in self._rooms_for_two()]}, pk=str(self.sitting1.pk))
            self.assertEqual(ok.status_code, 200, ok.data)
            self.assertEqual(ok.data["students"], 7)

            teacher = self._teacher("T9", login=True)
            ExamInvigilation.objects.create(sitting=self.sitting1, room=self.room_small, staff=teacher)
            request = self.factory.get("/x/")
            request.tenant = self.school
            force_authenticate(request, user=teacher.login_user)
            duties = MyDutiesView.as_view()(request)
            self.assertEqual([d["room"] for d in duties.data], ["R1"])
            request = self.factory.get("/x/")
            request.tenant = self.school
            force_authenticate(request, user=self.clerk)
            self.assertEqual(MyDutiesView.as_view()(request).data, [])  # not linked to a duty

    def test_a_bad_request_is_a_clear_400_and_changes_nothing(self):
        with tenant_context(self.school):
            tiny = self._call(ExamSittingViewSet, {"post": "allocate_rooms"}, "post", self.owner,
                              {"rooms": [str(self.room_small.id)]}, pk=str(self.sitting1.pk))
            self.assertEqual(tiny.status_code, 400)
            self.assertIn("short by", str(tiny.data))
            self.assertEqual(ExamSeat.objects.count(), 0)
            no_rooms = self._call(ExamSittingViewSet, {"post": "allocate_invigilators"}, "post", self.owner, {},
                                  pk=str(self.sitting1.pk))
            self.assertEqual(no_rooms.status_code, 400)

    def test_allocating_invigilators_notifies_those_with_a_login(self):
        with tenant_context(self.school):
            member = self.teachers[2]  # give T3 a login so there is someone to notify
            user = User.objects.create_user(username=f"t3_{uuid.uuid4().hex[:5]}@s.com", password="Password123!")
            member.profile.user_id = user.id
            member.profile.save()
            allocation.allocate_rooms(self.sitting1, room_ids=self._rooms_for_two())
            response = self._call(ExamSittingViewSet, {"post": "allocate_invigilators"}, "post", self.owner,
                                  {"per_room": 2}, pk=str(self.sitting1.pk))
            self.assertEqual(response.status_code, 200, response.data)
            note = Notification.objects.get(recipient_user_id=user.id)
            self.assertIn("Exam duty", note.title)
            self.assertIn("room", note.body)

    def test_the_duty_roster_lists_every_duty(self):
        with tenant_context(self.school):
            allocation.allocate_rooms(self.sitting1, room_ids=self._rooms_for_two())
            allocation.allocate_invigilators(self.sitting1, per_room=2)
            request = self.factory.get("/x/", {"examination": str(self.exam.pk)})
            request.tenant = self.school
            force_authenticate(request, user=self.owner)
            rows = DutyRosterView.as_view()(request).data
            self.assertEqual(len(rows), 4)
            self.assertEqual({r["examination"] for r in rows}, {"Term 1"})


class AdmitCardTests(AllocationBase):
    def _cards(self, user, section=None):
        from .allocation_views import AdmitCardsView

        request = self.factory.get("/x/", {"examination": str(self.exam.pk), "section": str((section or self.section_a).pk)})
        request.tenant = self.school
        force_authenticate(request, user=user)
        return AdmitCardsView.as_view()(request)

    def test_each_student_gets_their_papers_with_the_room_and_seat_from_the_plan(self):
        with tenant_context(self.school):
            allocation.allocate_rooms(self.sitting1)  # class A and B together in the Hall
            response = self._cards(self.owner)
            self.assertEqual(response.status_code, 200)
            data = response.data
            self.assertEqual(data["class"], "Grade 10 A")
            self.assertEqual([c["enrollment_id"] for c in data["cards"]], ["ENR-A1", "ENR-A2", "ENR-A3", "ENR-A4"])
            card = data["cards"][0]
            self.assertEqual([p["subject"] for p in card["papers"]], ["Math"])  # class A has one paper
            paper = card["papers"][0]
            seat = ExamSeat.objects.get(sitting=self.sitting1, student=self.students_a[0])
            self.assertEqual((paper["room"], paper["seat"]), ("Hall", seat.seat_number))
            seats = {c["name"]: c["papers"][0]["seat"] for c in data["cards"]}
            self.assertEqual(len(set(seats.values())), 4)  # nobody shares a seat

    def test_class_with_two_sittings_lists_both_papers_in_date_order(self):
        with tenant_context(self.school):
            allocation.allocate_rooms(self.sitting1)
            allocation.allocate_rooms(self.sitting2)
            papers = self._cards(self.owner, self.section_b).data["cards"][0]["papers"]
            self.assertEqual([p["subject"] for p in papers], ["English", "Math"])
            self.assertEqual([str(p["date"]) for p in papers], [str(DAY1), str(DAY2)])
            self.assertTrue(all(p["room"] == "Hall" and p["seat"] for p in papers))

    def test_without_a_seating_plan_the_paper_room_or_blank_is_shown(self):
        with tenant_context(self.school):
            self.paper_a.room = self.room_small
            self.paper_a.save()
            first = self._cards(self.owner).data["cards"][0]["papers"][0]
            self.assertEqual((first["room"], first["seat"]), ("R1", None))
            self.paper_b.room = None
            self.paper_b.save()
            second = self._cards(self.owner, self.section_b).data["cards"][0]["papers"][0]
            self.assertEqual((second["room"], second["seat"]), ("", None))

    def test_only_users_who_can_view_examinations_get_admit_cards(self):
        with tenant_context(self.school):
            self.assertEqual(self._cards(self.clerk).status_code, 403)


class DateSheetTests(AllocationBase):
    def setUp(self):
        super().setUp()
        from django.test import override_settings

        from families.models import Parent, StudentParentRelation

        with tenant_context(self.school):
            self.student = self.students_a[0]
            self.student_user = User.objects.create_user(username=f"kid_{uuid.uuid4().hex[:5]}@s.com", password="Password123!")
            self.student.profile.user_id = self.student_user.id
            self.student.profile.save()
            # One parent with a login, and one with only a phone number who agreed to WhatsApp.
            self.parent_user = User.objects.create_user(username=f"mum_{uuid.uuid4().hex[:5]}@s.com", password="Password123!")
            self.mum = Parent.objects.create(profile=Profile.objects.create(user_id=self.parent_user.id, first_name="Mum", last_name="P"))
            self.dad = Parent.objects.create(
                profile=Profile.objects.create(first_name="Dad", last_name="P", phone="9876543210"), whatsapp_opt_in=True
            )
            for parent in (self.mum, self.dad):
                StudentParentRelation.objects.create(student=self.student, parent=parent, relation_type="guardian")

    def _publish(self, user=None):
        from .views import ExaminationViewSet

        return self._call(ExaminationViewSet, {"post": "publish_date_sheet"}, "post", user or self.owner, {}, pk=str(self.exam.pk))

    def test_publishing_notifies_students_and_parents_once_per_announcement(self):
        from django.test import override_settings

        with override_settings(WHATSAPP_PROVIDER="console"), tenant_context(self.school):
            response = self._publish()
            self.assertEqual(response.status_code, 200, response.data)
            self.assertEqual(response.data["date_sheet_version"], 1)
            mine = Notification.objects.filter(recipient_user_id__in=[self.student_user.id, self.parent_user.id])
            self.assertEqual(mine.count(), 2)
            self.assertTrue(all("Date sheet" in n.title and "Term 1" in n.title for n in mine))
            self.assertTrue(all(self.student.profile.first_name in n.title for n in mine))
            self.assertEqual(AlertLog.objects.filter(kind="exam_date_sheet").count(), 3)  # student, mum, dad (WhatsApp)

            from notifications.models import WhatsAppOutboxEvent

            event = WhatsAppOutboxEvent.objects.get()
            self.assertEqual((event.template, event.to_phone), ("exam_date_sheet", "919876543210"))
            self.assertEqual(event.params[:2], [f"{self.student.profile.first_name} {self.student.profile.last_name}", "Term 1"])

            # Running the same announcement again sends nothing more.
            from .date_sheet import send_date_sheet_alerts

            send_date_sheet_alerts(self.exam.pk, 1)
            self.assertEqual(AlertLog.objects.filter(kind="exam_date_sheet").count(), 3)

            # Announcing again after a change is a new announcement and notifies everyone again.
            self.assertEqual(self._publish().data["date_sheet_version"], 2)
            self.assertEqual(Notification.objects.filter(recipient_user_id=self.student_user.id).count(), 2)

    def test_it_needs_papers_and_the_right_permission(self):
        with tenant_context(self.school):
            self.assertEqual(self._publish(self.clerk).status_code, 403)
            ExamSchedule.objects.all().delete()
            empty = self._publish()
            self.assertEqual(empty.status_code, 400)
            self.exam.refresh_from_db()
            self.assertEqual(self.exam.date_sheet_version, 0)

    def test_nothing_goes_to_whatsapp_without_opt_in_or_provider(self):
        from notifications.models import WhatsAppOutboxEvent

        with tenant_context(self.school):
            self._publish()  # provider is "disabled" by default
            self.assertEqual(WhatsAppOutboxEvent.objects.count(), 0)
            self.assertEqual(Notification.objects.filter(recipient_user_id=self.parent_user.id).count(), 1)


class MarksProgressTests(AllocationBase):
    def setUp(self):
        super().setUp()
        from academics.models import SubjectAssignment

        with tenant_context(self.school):
            # A teacher with a login for each of the first two papers (the same teacher for class A's Math).
            self.t_user = User.objects.create_user(username=f"tm_{uuid.uuid4().hex[:5]}@s.com", password="Password123!")
            self.teacher = self.teachers[4]
            self.teacher.profile.user_id = self.t_user.id
            self.teacher.profile.save()
            SubjectAssignment.objects.create(section=self.section_a, subject=self.math, instructor=self.teacher.instructor_record)
            SubjectAssignment.objects.create(section=self.section_b, subject=self.english, instructor=self.teacher.instructor_record)
            self.exam.marks_due_date = datetime.date(2026, 6, 10)
            self.exam.save()

    def _enter(self, paper, students, marks="50", attendance="present"):
        from .models import ExamMark

        for student in students:
            ExamMark.objects.create(
                exam_schedule=paper, student=student, marks_obtained=None if attendance != "present" and marks is None else marks,
                attendance=attendance,
            )

    def _progress(self, today=datetime.date(2026, 6, 5)):
        from .progress import schedule_progress

        return schedule_progress(self.exam, today)

    def test_progress_counts_scores_and_recorded_absences_but_not_blank_marks(self):
        with tenant_context(self.school):
            first = {row["subject"] + row["class"]: row for row in self._progress()["rows"]}
            self.assertEqual(first["MathGrade 10 A"]["state"], "not_started")

            self._enter(self.paper_a, self.students_a[:2])  # two scored
            self._enter(self.paper_a, self.students_a[2:3], marks=None, attendance="absent")  # one absent counts
            from .models import ExamMark

            ExamMark.objects.create(exam_schedule=self.paper_a, student=self.students_a[3], marks_obtained=None)  # blank
            row = next(r for r in self._progress()["rows"] if r["subject"] == "Math" and r["class"] == "Grade 10 A")
            self.assertEqual((row["entered"], row["expected"], row["state"]), (3, 4, "in_progress"))
            self.assertEqual(row["teachers"], ["T5 Teacher"])

            ExamMark.objects.filter(exam_schedule=self.paper_a, student=self.students_a[3]).update(marks_obtained="40")
            row = next(r for r in self._progress()["rows"] if r["class"] == "Grade 10 A")
            self.assertEqual((row["entered"], row["state"]), (4, "complete"))

    def test_papers_are_overdue_only_after_the_due_date_and_never_when_complete_or_locked(self):
        with tenant_context(self.school):
            self._enter(self.paper_a, self.students_a)  # class A Math complete
            self.paper_b2.is_locked = True
            self.paper_b2.save()
            before = self._progress(datetime.date(2026, 6, 10))
            self.assertEqual(before["summary"]["overdue"], 0)  # the due day itself is not late
            after = self._progress(datetime.date(2026, 6, 11))
            by_class = {(r["subject"], r["class"]): r for r in after["rows"]}
            self.assertFalse(by_class[("Math", "Grade 10 A")]["overdue"])  # complete
            self.assertFalse(by_class[("Math", "Grade 10 B")]["overdue"])  # locked
            self.assertTrue(by_class[("English", "Grade 10 B")]["overdue"])  # untouched and late
            self.assertEqual(after["summary"]["overdue"], 1)

    def test_reminders_go_to_assigned_teachers_once_and_note_unassigned_papers(self):
        from .progress import remind_pending_marks

        with tenant_context(self.school):
            self._enter(self.paper_a, self.students_a[:1])
            first = remind_pending_marks(self.exam, datetime.date(2026, 6, 11))
            self.assertEqual(first["teachers"], 1)
            self.assertEqual(first["unassigned"], 1)  # class B's Math (paper_b2) has no teacher assigned
            note = Notification.objects.get(recipient_user_id=self.t_user.id)
            self.assertIn("Marks pending", note.title)
            self.assertIn("Math Grade 10 A (1/4)", note.body)
            self.assertIn("It was due on 10 Jun 2026", note.body)

            again = remind_pending_marks(self.exam, datetime.date(2026, 6, 11))
            self.assertEqual((again["teachers"], again["already_reminded"]), (0, 1))
            self.assertEqual(Notification.objects.filter(recipient_user_id=self.t_user.id).count(), 1)

    def test_nothing_is_sent_when_everything_is_in(self):
        from .progress import remind_pending_marks

        with tenant_context(self.school):
            self._enter(self.paper_a, self.students_a)
            self._enter(self.paper_b, self.students_b)
            self._enter(self.paper_b2, self.students_b)
            self.assertEqual(remind_pending_marks(self.exam)["teachers"], 0)
            self.assertEqual(Notification.objects.filter(recipient_user_id=self.t_user.id).count(), 0)

    def test_the_api_shows_progress_and_only_managers_can_send_reminders(self):
        from .allocation_views import MarksProgressView
        from .views import ExaminationViewSet

        with tenant_context(self.school):
            request = self.factory.get("/x/", {"examination": str(self.exam.pk)})
            request.tenant = self.school
            force_authenticate(request, user=self.owner)
            data = MarksProgressView.as_view()(request).data
            self.assertEqual(data["summary"]["papers"], 3)
            self.assertEqual(str(data["due_date"]), "2026-06-10")

            denied = self._call(ExaminationViewSet, {"post": "remind_marks"}, "post", self.clerk, {}, pk=str(self.exam.pk))
            self.assertEqual(denied.status_code, 403)
            sent = self._call(ExaminationViewSet, {"post": "remind_marks"}, "post", self.owner, {}, pk=str(self.exam.pk))
            self.assertEqual(sent.status_code, 200, sent.data)
            self.assertEqual(sent.data["teachers"], 1)

    def test_the_daily_job_only_chases_examinations_that_are_due_or_late(self):
        from .progress import remind_all_schools

        with tenant_context(self.school):
            # Due on 10 June: nothing on the 5th, a reminder on the 9th (due within a day).
            from unittest import mock

            with mock.patch("examinations.progress.school_today", return_value=datetime.date(2026, 6, 5)):
                self.assertEqual(remind_all_schools()["examinations"], 0)
            with mock.patch("examinations.progress.school_today", return_value=datetime.date(2026, 6, 9)):
                self.assertEqual(remind_all_schools(), {"examinations": 1, "teachers": 1})


class RankListTests(AllocationBase):
    def _result(self, student, percentage, passed=True):
        from .models import ExamResult

        return ExamResult.objects.create(
            examination=self.exam, student=student, academic_year="2026",
            total_marks_obtained=Decimal(percentage), total_max_marks=Decimal("100"), percentage=Decimal(percentage),
            overall_grade="A", is_pass=passed,
        )

    def _publish(self):
        self.exam.is_published = True
        self.exam.save()

    def _ranks(self, user=None, **params):
        from .allocation_views import RankListView

        request = self.factory.get("/x/", {"examination": str(self.exam.pk), **params})
        request.tenant = self.school
        force_authenticate(request, user=user or self.owner)
        return RankListView.as_view()(request)

    def test_ties_share_a_rank_and_the_next_rank_is_skipped(self):
        with tenant_context(self.school):
            a1, a2, a3, a4 = self.students_a
            self._result(a1, "90")
            self._result(a2, "85")
            self._result(a3, "85")
            self._result(a4, "70")
            self._publish()
            data = self._ranks(section=str(self.section_a.pk)).data
            self.assertEqual(data["title"], "Grade 10 A")
            self.assertEqual([(r["name"], r["rank"]) for r in data["rows"]],
                             [("A1 Pupil", 1), ("A2 Pupil", 2), ("A3 Pupil", 2), ("A4 Pupil", 4)])
            self.assertEqual([r["rank"] for r in data["toppers"]], [1, 2, 2])  # the top three places, ties included

    def test_failed_students_are_listed_unranked_unless_asked_for(self):
        with tenant_context(self.school):
            a1, a2, a3, _ = self.students_a
            self._result(a1, "80")
            self._result(a2, "20", passed=False)
            self._result(a3, "60")
            self._publish()
            default = self._ranks(section=str(self.section_a.pk)).data["rows"]
            self.assertEqual([(r["name"], r["rank"]) for r in default], [("A1 Pupil", 1), ("A3 Pupil", 2), ("A2 Pupil", None)])
            everyone = self._ranks(section=str(self.section_a.pk), include_failed="true").data["rows"]
            self.assertEqual([r["rank"] for r in everyone], [1, 2, 3])

    def test_a_class_list_ranks_across_its_sections(self):
        with tenant_context(self.school):
            self._result(self.students_a[0], "70")
            self._result(self.students_b[0], "95")
            self._publish()
            rows = self._ranks(level=str(self.section_a.level.pk)).data["rows"]
            self.assertEqual([(r["name"], r["class"], r["rank"]) for r in rows],
                             [("B1 Pupil", "Grade 10 B", 1), ("A1 Pupil", "Grade 10 A", 2)])

    def test_nothing_is_ranked_before_publication_or_without_a_scope_or_permission(self):
        with tenant_context(self.school):
            self._result(self.students_a[0], "70")
            self.assertEqual(self._ranks(section=str(self.section_a.pk)).status_code, 400)  # not published
            self._publish()
            self.assertEqual(self._ranks().status_code, 400)  # neither section nor class
            self.assertEqual(self._ranks(section=str(self.section_a.pk), level=str(self.section_a.level.pk)).status_code, 400)
            self.assertEqual(self._ranks(self.clerk, section=str(self.section_a.pk)).status_code, 403)


class SelfServiceTests(AllocationBase):
    """What students and parents may see: the announced date sheet, their own admit card, and a rank if enabled."""

    def setUp(self):
        super().setUp()
        from families.models import Parent, StudentParentRelation

        with tenant_context(self.school):
            self.kid = self.students_a[0]
            self.kid_user = User.objects.create_user(username=f"kid_{uuid.uuid4().hex[:5]}@s.com", password="Password123!")
            self.kid.profile.user_id = self.kid_user.id
            self.kid.profile.save()
            UserRole.objects.create(user=self.kid_user, role=Role.objects.get(slug="student"))

            self.mum_user = User.objects.create_user(username=f"mum_{uuid.uuid4().hex[:5]}@s.com", password="Password123!")
            mum_profile = Profile.objects.create(user_id=self.mum_user.id, first_name="Mum", last_name="P")
            # Like any school that lets parents see results, grant the parent role the permission the portal needs.
            from roles.models import Permission

            Role.objects.get(slug="parent").permissions.add(Permission.objects.get(codename="view_child_results"))
            UserRole.objects.create(user=self.mum_user, role=Role.objects.get(slug="parent"))
            self.mum = Parent.objects.create(profile=mum_profile)
            StudentParentRelation.objects.create(student=self.kid, parent=self.mum, relation_type="mother")

            self.other_user = User.objects.create_user(username=f"oth_{uuid.uuid4().hex[:5]}@s.com", password="Password123!")
            other_profile = Profile.objects.create(user_id=self.other_user.id, first_name="Other", last_name="P")
            UserRole.objects.create(user=self.other_user, role=Role.objects.get(slug="parent"))
            Parent.objects.create(profile=other_profile)  # a parent of nobody here

    def _get(self, view, user, params=None, **kwargs):
        request = self.factory.get("/x/", params or {})
        request.tenant = self.school
        force_authenticate(request, user=user)
        return view.as_view()(request, **kwargs)

    def _announce(self):
        Examination.objects.filter(pk=self.exam.pk).update(date_sheet_version=1)

    def test_nothing_is_visible_until_the_school_announces_the_date_sheet(self):
        from parent_portal.views import ChildAdmitCardView, ChildExamsView

        from .allocation_views import MyAdmitCardView, MyExamsView

        with tenant_context(self.school):
            self.assertEqual(self._get(MyExamsView, self.kid_user).data, [])
            self.assertEqual(self._get(MyAdmitCardView, self.kid_user, {"examination": str(self.exam.pk)}).status_code, 404)
            self.assertEqual(self._get(ChildExamsView, self.mum_user, student_id=self.kid.pk).data, [])
            self.assertEqual(
                self._get(ChildAdmitCardView, self.mum_user, {"examination": str(self.exam.pk)}, student_id=self.kid.pk).status_code, 404
            )

    def test_a_student_sees_only_their_own_admit_card_with_room_and_seat(self):
        from .allocation_views import MyAdmitCardView, MyExamsView

        with tenant_context(self.school):
            allocation.allocate_rooms(self.sitting1)
            self._announce()
            listed = self._get(MyExamsView, self.kid_user).data
            self.assertEqual([e["name"] for e in listed], ["Term 1"])

            data = self._get(MyAdmitCardView, self.kid_user, {"examination": str(self.exam.pk)}).data
            self.assertEqual(len(data["cards"]), 1)
            card = data["cards"][0]
            self.assertEqual(card["enrollment_id"], "ENR-A1")
            self.assertEqual([p["subject"] for p in card["papers"]], ["Math"])
            seat = ExamSeat.objects.get(sitting=self.sitting1, student=self.kid)
            self.assertEqual((card["papers"][0]["room"], card["papers"][0]["seat"]), ("Hall", seat.seat_number))

    def test_a_parent_sees_their_childs_card_and_no_other_parent_can(self):
        from parent_portal.views import ChildAdmitCardView, ChildExamsView

        with tenant_context(self.school):
            self._announce()
            params = {"examination": str(self.exam.pk)}
            self.assertEqual(len(self._get(ChildExamsView, self.mum_user, student_id=self.kid.pk).data), 1)
            mine = self._get(ChildAdmitCardView, self.mum_user, params, student_id=self.kid.pk)
            self.assertEqual((mine.status_code, mine.data["cards"][0]["enrollment_id"]), (200, "ENR-A1"))
            # A parent whose child is someone else's is refused.
            self.assertEqual(self._get(ChildAdmitCardView, self.other_user, params, student_id=self.kid.pk).status_code, 403)
            self.assertEqual(self._get(ChildExamsView, self.other_user, student_id=self.kid.pk).status_code, 403)

    def test_ranks_reach_families_only_when_the_school_turns_them_on(self):
        from .models import ExamResult, ExaminationSettings
        from .self_service import family_ranks

        with tenant_context(self.school):
            for student, pct in zip(self.students_a[:3], ("90", "80", "20")):
                ExamResult.objects.create(
                    examination=self.exam, student=student, academic_year="2026", total_marks_obtained=Decimal(pct),
                    total_max_marks=Decimal("100"), percentage=Decimal(pct), overall_grade="A", is_pass=pct != "20",
                )
            Examination.objects.filter(pk=self.exam.pk).update(is_published=True)
            self.assertEqual(family_ranks(self.kid), {})  # off by default

            ExaminationSettings.objects.update_or_create(singleton=True, defaults={"show_rank_to_families": True})
            mine = family_ranks(self.kid)[str(self.exam.pk)]
            self.assertEqual((mine["rank"], mine["of"], mine["section"]), (1, 3, "Grade 10 A"))
            self.assertEqual(family_ranks(self.students_a[1])[str(self.exam.pk)]["rank"], 2)
            self.assertEqual(family_ranks(self.students_a[2]), {})  # a student who did not pass gets no rank

    def test_the_report_card_a_parent_opens_carries_the_ranks(self):
        from unittest import mock

        from parent_portal.views import ChildReportCardView

        with tenant_context(self.school):
            with mock.patch("examinations.services.build_student_report_card", return_value={"examinations": []}):
                with mock.patch("examinations.self_service.family_ranks", return_value={"x": {"rank": 1}}):
                    card = self._get(ChildReportCardView, self.mum_user, student_id=self.kid.pk)
            self.assertEqual(card.status_code, 200, card.data)
            self.assertEqual(card.data["ranks"], {"x": {"rank": 1}})

    def test_the_settings_accept_either_setting_and_nothing_else(self):
        from .views import ExaminationSettingsView

        def patch(user, data):
            request = self.factory.patch("/x/", data, format="json")
            request.tenant = self.school
            force_authenticate(request, user=user)
            return ExaminationSettingsView.as_view()(request)

        with tenant_context(self.school):
            got = self._get(ExaminationSettingsView, self.owner)
            self.assertEqual((got.data["show_rank_to_families"], got.data["require_separate_publisher"]), (False, False))
            ok = patch(self.owner, {"show_rank_to_families": True})
            self.assertEqual((ok.status_code, ok.data["show_rank_to_families"], ok.data["require_separate_publisher"]), (200, True, False))
            both = patch(self.owner, {"show_rank_to_families": False, "require_separate_publisher": True})
            self.assertEqual((both.data["show_rank_to_families"], both.data["require_separate_publisher"]), (False, True))
            for bad in ({}, {"other": True}, {"show_rank_to_families": "yes"}, {"show_rank_to_families": True, "other": True}):
                self.assertEqual(patch(self.owner, bad).status_code, 400, bad)
            self.assertEqual(patch(self.clerk, {"show_rank_to_families": True}).status_code, 403)


class AnalyticsTests(AllocationBase):
    """Class A: Math 90/60/50/20 and English 90/60/30/40 (pass mark 35). Class B: one pass, one borderline, one absent."""

    def _result(self, student, math, english):
        """``math``/``english`` are a percentage, or None for absent. A subject below 35 is a fail."""
        from .models import ExamResult

        def entry(subject, name, pct):
            if pct is None:
                return {"subject": str(subject.pk), "subject_name": name, "marks_obtained": None, "max_marks": 100.0,
                        "percentage": None, "grade": None, "is_absent": True, "is_pass": False}
            return {"subject": str(subject.pk), "subject_name": name, "marks_obtained": float(pct), "max_marks": 100.0,
                    "percentage": float(pct), "grade": "A", "is_absent": False, "is_pass": pct >= 35}

        breakdown = [entry(self.math, "Math", math), entry(self.english, "English", english)]
        sat = [b["percentage"] for b in breakdown if b["percentage"] is not None]
        overall = sum(sat) / len(breakdown) if len(sat) == len(breakdown) else sum(sat) / len(sat)
        passed = all(b["is_pass"] for b in breakdown if not b["is_absent"])
        return ExamResult.objects.create(
            examination=self.exam, student=student, academic_year="2026", total_marks_obtained=Decimal(str(overall)),
            total_max_marks=Decimal("100"), percentage=Decimal(str(overall)), overall_grade="A", is_pass=passed,
            subject_breakdown=breakdown,
        )

    def _seed(self):
        for student, math, english in zip(self.students_a, (90, 60, 50, 20), (90, 60, 30, 40)):
            self._result(student, math, english)
        for student, math, english in zip(self.students_b, (80, 36, 70), (80, 36, None)):
            self._result(student, math, english)
        Examination.objects.filter(pk=self.exam.pk).update(is_published=True)
        self.exam.refresh_from_db()

    def _api(self, view, user=None, **params):
        request = self.factory.get("/x/", {k: str(v) for k, v in params.items()})
        request.tenant = self.school
        force_authenticate(request, user=user or self.owner)
        return view.as_view()(request)

    def test_a_sections_overall_figures_and_distribution(self):
        from .analytics import exam_analytics

        with tenant_context(self.school):
            self._seed()
            data = exam_analytics(self.exam, section=self.section_a)
            self.assertEqual(data["title"], "Grade 10 A")
            self.assertEqual(
                data["overall"],
                {"students": 4, "passed": 2, "failed": 2, "pass_percentage": 50.0, "average_percentage": 55.0,
                 "highest_percentage": 90.0, "lowest_percentage": 30.0},
            )
            counts = {b["label"]: b["count"] for b in data["distribution"]}
            self.assertEqual(counts, {"Below 35": 1, "35-49": 1, "50-59": 0, "60-74": 1, "75-89": 0, "90 and above": 1})

    def test_subjects_use_each_papers_own_pass_result_and_the_weakest_comes_first(self):
        from .analytics import exam_analytics

        with tenant_context(self.school):
            self._seed()
            subjects = {s["subject"]: s for s in exam_analytics(self.exam, section=self.section_a)["subjects"]}
            self.assertEqual((subjects["Math"]["passed"], subjects["Math"]["pass_percentage"], subjects["Math"]["average_percentage"]), (3, 75.0, 55.0))
            self.assertEqual((subjects["English"]["passed"], subjects["English"]["average_percentage"]), (3, 55.0))
            self.assertEqual((subjects["Math"]["highest_percentage"], subjects["Math"]["lowest_percentage"]), (90.0, 20.0))

            whole = exam_analytics(self.exam, level=self.section_a.level)
            english = next(s for s in whole["subjects"] if s["subject"] == "English")
            self.assertEqual((english["appeared"], english["absent"]), (6, 1))  # an absent student is counted apart
            self.assertEqual([r["section"] for r in whole["sections"]], ["Grade 10 A", "Grade 10 B"])
            self.assertEqual(whole["overall"]["students"], 7)

    def test_two_examinations_are_compared_subject_by_subject(self):
        from .analytics import compare_examinations
        from .models import ExamResult

        with tenant_context(self.school):
            self._seed()
            later = Examination.objects.create(
                academic_year="2026", name="Term 2", exam_type=self.exam_type, start_date=DAY2, end_date=DAY2, is_published=True
            )
            for student, math, english in zip(self.students_a, (95, 65, 55, 25), (90, 60, 30, 40)):
                entries = [
                    {"subject": str(self.math.pk), "subject_name": "Math", "marks_obtained": float(math), "max_marks": 100.0,
                     "percentage": float(math), "grade": "A", "is_absent": False, "is_pass": math >= 35},
                    {"subject": str(self.english.pk), "subject_name": "English", "marks_obtained": float(english), "max_marks": 100.0,
                     "percentage": float(english), "grade": "A", "is_absent": False, "is_pass": english >= 35},
                ]
                ExamResult.objects.create(
                    examination=later, student=student, academic_year="2026", total_marks_obtained=Decimal("1"),
                    total_max_marks=Decimal("100"), percentage=Decimal(str((math + english) / 2)),
                    overall_grade="A", is_pass=all(e["is_pass"] for e in entries), subject_breakdown=entries,
                )
            data = compare_examinations(self.exam, later, section=self.section_a)
            rows = {r["subject"]: r for r in data["subjects"]}
            self.assertEqual((rows["Math"]["first_average"], rows["Math"]["second_average"], rows["Math"]["change"]), (55.0, 60.0, 5.0))
            self.assertEqual(rows["English"]["change"], 0.0)
            self.assertEqual((data["first"]["name"], data["second"]["name"]), ("Term 1", "Term 2"))

    def test_the_weak_student_list_orders_failures_first_and_flags_borderline_and_absent(self):
        from .analytics import weak_students

        with tenant_context(self.school):
            self._seed()
            data = weak_students(self.exam, level=self.section_a.level)
            names = [r["name"] for r in data["rows"]]
            # A4 failed Math (30%), A3 failed English (40%); B2 is borderline in both subjects; B3 missed English.
            self.assertEqual(names, ["A4 Pupil", "A3 Pupil", "B2 Pupil", "B3 Pupil"])
            by_name = {r["name"]: r for r in data["rows"]}
            self.assertEqual([(w["subject"], w["status"]) for w in by_name["A4 Pupil"]["weak_subjects"]], [("Math", "failed")])
            self.assertEqual({(w["subject"], w["status"]) for w in by_name["B2 Pupil"]["weak_subjects"]},
                             {("Math", "borderline"), ("English", "borderline")})
            self.assertEqual([(w["subject"], w["status"]) for w in by_name["B3 Pupil"]["weak_subjects"]], [("English", "absent")])
            self.assertTrue(all("attendance_percentage" in r for r in data["rows"]))
            # A wider margin catches more students; a student with 60% and 90% is never listed.
            self.assertNotIn("A1 Pupil", names)
            self.assertNotIn("A2 Pupil", names)

    def test_reports_wait_for_publication_need_a_scope_and_the_permission(self):
        from .allocation_views import AnalyticsCompareView, AnalyticsView, WeakStudentsView

        with tenant_context(self.school):
            self._seed()
            Examination.objects.filter(pk=self.exam.pk).update(is_published=False)
            section = str(self.section_a.pk)
            for view in (AnalyticsView, WeakStudentsView):
                self.assertEqual(self._api(view, examination=self.exam.pk, section=section).status_code, 400)  # not published
            Examination.objects.filter(pk=self.exam.pk).update(is_published=True)

            ok = self._api(AnalyticsView, examination=self.exam.pk, section=section)
            self.assertEqual((ok.status_code, ok.data["overall"]["students"]), (200, 4))
            self.assertEqual(self._api(AnalyticsView, examination=self.exam.pk).status_code, 400)  # no scope
            self.assertEqual(self._api(WeakStudentsView, examination=self.exam.pk, section=section, margin=10).status_code, 200)
            for view in (AnalyticsView, WeakStudentsView):
                self.assertEqual(self._api(view, self.clerk, examination=self.exam.pk, section=section).status_code, 403)
            both = self._api(AnalyticsCompareView, examination=self.exam.pk, other=self.exam.pk, section=section)
            self.assertEqual(both.status_code, 200)
            self.assertTrue(all(r["change"] == 0.0 for r in both.data["subjects"]))


class ModerationTests(AllocationBase):
    """Class A's Math paper (max 100, pass 35): four students scored 30, 33, 50 and 98, one was absent."""

    def setUp(self):
        super().setUp()
        from .models import ExamMark

        with tenant_context(self.school):
            self.marks = {}
            for student, value in zip(self.students_a[:4], ("30", "33", "50", "98")):
                self.marks[student.enrollment_id] = ExamMark.objects.create(
                    exam_schedule=self.paper_a, student=student, marks_obtained=Decimal(value), attendance="present"
                )

    def _preview(self, **options):
        from .moderation import preview_moderation

        return preview_moderation(self.paper_a, **options)

    def _apply(self, user=None, **options):
        from .moderation import apply_moderation

        options.setdefault("reason", "Paper was harder than planned")
        return apply_moderation(self.paper_a, user_id=(user or self.owner).id, **options)

    def _current(self):
        from .models import ExamMark

        return {m.student.enrollment_id: m.marks_obtained for m in ExamMark.objects.filter(exam_schedule=self.paper_a).select_related("student")}

    def test_a_preview_shows_the_effect_and_changes_nothing(self):
        from .models import ExamMarkChange

        with tenant_context(self.school):
            result = self._preview(method="add", value="5")
            summary = result["summary"]
            self.assertEqual((summary["students_with_marks"], summary["changed"], summary["capped"]), (4, 4, 1))
            self.assertEqual((summary["passed_before"], summary["passed_after"]), (2, 4))  # 30 and 33 now reach 35 and 38
            self.assertEqual((summary["average_before"], summary["average_after"]), (52.75, 57.0))  # 98 stops at 100
            rows = {r["enrollment_id"]: r for r in result["rows"]}
            self.assertEqual((rows["ENR-A4"]["old"], rows["ENR-A4"]["new"]), (Decimal("98"), Decimal("100")))
            self.assertEqual((rows["ENR-A1"]["passed_before"], rows["ENR-A1"]["passed_after"]), (False, True))
            self.assertEqual(self._current()["ENR-A1"], Decimal("30"))  # untouched
            self.assertEqual(ExamMarkChange.objects.count(), 0)

    def test_applying_changes_the_marks_and_keeps_a_history_row_for_each(self):
        from .models import ExamMarkChange

        with tenant_context(self.school):
            result = self._apply(method="add", value="5", expected_changed=4)
            self.assertEqual(result["changed"], 4)
            self.assertEqual(self._current(), {"ENR-A1": Decimal("35"), "ENR-A2": Decimal("38"), "ENR-A3": Decimal("55"), "ENR-A4": Decimal("100")})
            history = ExamMarkChange.objects.filter(kind="moderation")
            self.assertEqual(history.count(), 4)
            first = history.get(mark=self.marks["ENR-A1"])
            self.assertEqual((first.old_marks, first.new_marks, first.reason, first.changed_by_user_id), (Decimal("30"), Decimal("35"), "Paper was harder than planned", self.owner.id))

    def test_scaling_rounds_to_the_chosen_step_and_is_capped_at_the_maximum(self):
        with tenant_context(self.school):
            whole = {r["enrollment_id"]: r["new"] for r in self._preview(method="scale", value="1.1")["rows"]}
            self.assertEqual(whole, {"ENR-A1": Decimal("33"), "ENR-A2": Decimal("36"), "ENR-A3": Decimal("55"), "ENR-A4": Decimal("100")})
            half = {r["enrollment_id"]: r["new"] for r in self._preview(method="scale", value="1.1", step="0.5")["rows"]}
            self.assertEqual(half["ENR-A2"], Decimal("36.5"))  # 36.3 to the nearest half mark

    def test_it_can_be_limited_to_students_below_a_mark(self):
        with tenant_context(self.school):
            self._apply(method="add", value="5", below="40")
            self.assertEqual(self._current(), {"ENR-A1": Decimal("35"), "ENR-A2": Decimal("38"), "ENR-A3": Decimal("50"), "ENR-A4": Decimal("98")})

    def test_grace_marks_already_given_count_towards_the_maximum_and_absentees_are_untouched(self):
        from .models import ExamMark

        with tenant_context(self.school):
            ExamMark.objects.filter(pk=self.marks["ENR-A4"].pk).update(grace_marks=Decimal("1"))  # 98 + 1 grace
            absent = ExamMark.objects.create(
                exam_schedule=self.paper_a, student=self.students_b[0], marks_obtained=None, attendance="absent"
            )
            rows = {r["enrollment_id"]: r for r in self._preview(method="add", value="5")["rows"]}
            self.assertEqual(rows["ENR-A4"]["new"], Decimal("99"))  # 99 + 1 grace = 100, no more
            self.assertNotIn(absent.student.enrollment_id, rows)

    def test_published_papers_and_papers_with_score_parts_are_refused(self):
        from .models import ExamScheduleComponent
        from .moderation import ModerationError

        with tenant_context(self.school):
            ExamScheduleComponent.objects.create(
                exam_schedule=self.paper_a, name="Theory", code="TH", max_marks=Decimal("100"), pass_marks=Decimal("35")
            )
            with self.assertRaises(ModerationError) as parts:
                self._preview(method="add", value="5")
            self.assertIn("score parts", str(parts.exception))
            ExamScheduleComponent.objects.all().delete()

            Examination.objects.filter(pk=self.exam.pk).update(is_published=True)
            self.paper_a.refresh_from_db()
            with self.assertRaises(ModerationError) as published:
                self._apply(method="add", value="5")
            self.assertIn("published", str(published.exception))
            self.assertEqual(self._current()["ENR-A1"], Decimal("30"))

    def test_a_reason_is_required_and_stale_previews_and_empty_changes_are_refused(self):
        from .moderation import ModerationError
        from .models import ExamMark

        with tenant_context(self.school):
            for bad_reason in ("", "  ", "no"):
                with self.assertRaises(ModerationError):
                    self._apply(method="add", value="5", reason=bad_reason)
            with self.assertRaises(ModerationError) as stale:
                self._apply(method="add", value="5", expected_changed=3)  # the preview said 4
            self.assertIn("Preview again", str(stale.exception))
            with self.assertRaises(ModerationError):
                self._apply(method="add", value="0")  # nothing would change
            self.assertEqual(self._current()["ENR-A1"], Decimal("30"))
            self.assertEqual(ExamMark.objects.filter(exam_schedule=self.paper_a).count(), 4)

    def test_invalid_choices_are_refused(self):
        from .moderation import ModerationError

        with tenant_context(self.school):
            for options in (
                {"method": "halve", "value": "1"},
                {"method": "scale", "value": "0"},
                {"method": "scale", "value": "-2"},
                {"method": "add", "value": "abc"},
                {"method": "add", "value": "5", "step": "3"},
            ):
                with self.assertRaises(ModerationError, msg=str(options)):
                    self._preview(**options)

    def test_only_users_who_may_moderate_can_preview_or_apply(self):
        from .allocation_views import ModerationApplyView, ModerationPreviewView

        def post(view, user, data):
            request = self.factory.post("/x/", data, format="json")
            request.tenant = self.school
            force_authenticate(request, user=user)
            return view.as_view()(request, schedule_id=self.paper_a.pk)

        with tenant_context(self.school):
            body = {"method": "add", "value": "5", "reason": "Harder paper"}
            self.assertEqual(post(ModerationPreviewView, self.clerk, body).status_code, 403)
            self.assertEqual(post(ModerationApplyView, self.clerk, body).status_code, 403)
            preview = post(ModerationPreviewView, self.owner, body)
            self.assertEqual((preview.status_code, preview.data["summary"]["changed"]), (200, 4))
            applied = post(ModerationApplyView, self.owner, {**body, "expected_changed": 4})
            self.assertEqual((applied.status_code, applied.data["changed"]), (200, 4))
            bad = post(ModerationApplyView, self.owner, {**body, "method": "nope"})
            self.assertEqual(bad.status_code, 400)
