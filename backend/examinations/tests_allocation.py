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
