import datetime
import uuid as uuid_module

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import connection
from django.test import TransactionTestCase
from django.utils import timezone
from django_tenants.utils import tenant_context
from rest_framework.test import APIRequestFactory, force_authenticate

from academics.models import AcademicLevel, AcademicYear, Program, Section
from families.models import Parent, StudentParentRelation
from organizations.models import Domain, Organization
from profiles.models import Profile
from roles.models import Role, UserRole
from roles.signals import seed_default_roles
from staff.models import StaffMember
from students.models import Student, StudentLevel

from .models import PTMSession, PTMSlot
from .serializers import PTMSessionSerializer, PTMSlotSerializer
from .services import (
    block_slot,
    book_slot,
    cancel_booking,
    generate_slots_for_session,
    record_slot_feedback,
    unblock_slot,
)
from .views import (
    ParentAvailableSlotsView,
    ParentBookSlotView,
    ParentCancelBookingView,
    ParentMyBookingsView,
    ParentPTMSessionsView,
    PTMSessionViewSet,
    PTMSlotViewSet,
    TeacherScheduleView,
)

User = get_user_model()

# Booking is closed once a session date has passed, so test sessions are always in the future.
FUTURE = datetime.date.today() + datetime.timedelta(days=30)


class PTMFixtureMixin:
    def _build_school(self, schema_name=None, domain=None, name="PTM Test School"):
        suffix = uuid_module.uuid4().hex[:8]
        schema_name = schema_name or f"ptm_{suffix}"
        domain = domain or f"ptm-{suffix}.localhost"
        connection.set_schema_to_public()
        school = Organization.objects.create(schema_name=schema_name, name=name)
        Domain.objects.create(domain=domain, tenant=school, is_primary=True)
        return school


class PTMIntegrationTest(PTMFixtureMixin, TransactionTestCase):
    def setUp(self):
        self.school = self._build_school()
        self.factory = APIRequestFactory()

        with tenant_context(self.school):
            seed_default_roles()

            self.ay, _ = AcademicYear.objects.get_or_create(
                name="2026-27",
                defaults={
                    "start_date": datetime.date(2026, 4, 1),
                    "end_date": datetime.date(2027, 3, 31),
                    "is_current": True,
                },
            )

            # Owner user
            self.owner_user = User.objects.create_user(
                username=f"owner_{uuid_module.uuid4().hex[:6]}@school.com",
                email="owner@school.com",
                password="OwnerPassword123!",
            )
            owner_role = Role.objects.get(slug="owner")
            UserRole.objects.create(user=self.owner_user, role=owner_role)

            # Teacher 1
            t1_user = User.objects.create_user(
                username=f"t1_{uuid_module.uuid4().hex[:6]}@school.com",
                email="teacher1@school.com",
                password="TeacherPassword123!",
            )
            t1_role = Role.objects.get(slug="instructor")
            UserRole.objects.create(user=t1_user, role=t1_role)
            t1_profile = Profile.objects.create(
                user_id=t1_user.id,
                first_name="Anita",
                last_name="Sharma",
                email="teacher1@school.com",
            )
            self.teacher_1 = StaffMember.objects.create(
                profile=t1_profile,
                employee_id="EMP-T1",
                designation="Mathematics Teacher",
                department="Science",
            )

            # Teacher 2
            t2_user = User.objects.create_user(
                username=f"t2_{uuid_module.uuid4().hex[:6]}@school.com",
                email="teacher2@school.com",
                password="TeacherPassword123!",
            )
            UserRole.objects.create(user=t2_user, role=t1_role)
            t2_profile = Profile.objects.create(
                user_id=t2_user.id,
                first_name="Rajesh",
                last_name="Kumar",
                email="teacher2@school.com",
            )
            self.teacher_2 = StaffMember.objects.create(
                profile=t2_profile,
                employee_id="EMP-T2",
                designation="English Teacher",
                department="Languages",
            )

            # Program, Level, Section
            self.program = Program.objects.create(name="Secondary", code="SEC")
            self.level = AcademicLevel.objects.create(
                program=self.program, name="Grade 10", order=10
            )
            self.section = Section.objects.create(level=self.level, name="A")

            # Student 1
            s1_user = User.objects.create_user(
                username=f"s1_{uuid_module.uuid4().hex[:6]}@school.com",
                email="s1@school.com",
            )
            s1_profile = Profile.objects.create(
                user_id=s1_user.id,
                first_name="Rohan",
                last_name="Gupta",
            )
            self.student_1 = Student.objects.create(
                profile=s1_profile,
                enrollment_id="STU-001",
                status="active",
            )
            StudentLevel.objects.create(
                student=self.student_1,
                level=self.level,
                section=self.section,
                academic_year=self.ay,
                is_current=True,
            )

            # Student 2
            s2_user = User.objects.create_user(
                username=f"s2_{uuid_module.uuid4().hex[:6]}@school.com",
                email="s2@school.com",
            )
            s2_profile = Profile.objects.create(
                user_id=s2_user.id,
                first_name="Pooja",
                last_name="Verma",
            )
            self.student_2 = Student.objects.create(
                profile=s2_profile,
                enrollment_id="STU-002",
                status="active",
            )
            StudentLevel.objects.create(
                student=self.student_2,
                level=self.level,
                section=self.section,
                academic_year=self.ay,
                is_current=True,
            )

            # Parent 1 (linked to Student 1)
            self.p1_user = User.objects.create_user(
                username=f"p1_{uuid_module.uuid4().hex[:6]}@school.com",
                email="p1@school.com",
                password="ParentPassword123!",
            )
            parent_role = Role.objects.get(slug="parent")
            p1_profile = Profile.objects.create(
                user_id=self.p1_user.id,
                first_name="Suresh",
                last_name="Gupta",
                phone="9876543210",
            )
            self.parent_1 = Parent.objects.create(profile=p1_profile)
            # The profile comes first: assigning the role would otherwise create a second, blank one.
            UserRole.objects.create(user=self.p1_user, role=parent_role)
            StudentParentRelation.objects.create(
                student=self.student_1,
                parent=self.parent_1,
                relation_type="father",
                is_primary_contact=True,
            )

            # Parent 2 (linked to Student 2)
            self.p2_user = User.objects.create_user(
                username=f"p2_{uuid_module.uuid4().hex[:6]}@school.com",
                email="p2@school.com",
                password="ParentPassword123!",
            )
            p2_profile = Profile.objects.create(
                user_id=self.p2_user.id,
                first_name="Sunita",
                last_name="Verma",
                phone="9876543211",
            )
            self.parent_2 = Parent.objects.create(profile=p2_profile)
            # The profile comes first: assigning the role would otherwise create a second, blank one.
            UserRole.objects.create(user=self.p2_user, role=parent_role)
            StudentParentRelation.objects.create(
                student=self.student_2,
                parent=self.parent_2,
                relation_type="mother",
                is_primary_contact=True,
            )

    def test_session_creation_and_slot_generation(self):
        """Admin creates a PTM Session and auto-generates discrete time slots."""
        with tenant_context(self.school):
            session = PTMSession.objects.create(
                title="Term 1 Mid-Term PTM",
                academic_year=self.ay,
                meeting_date=FUTURE,
                start_time=datetime.time(9, 0),
                end_time=datetime.time(10, 0),  # 60 mins total
                slot_duration_minutes=15,       # 4 slots per teacher
                buffer_minutes=0,
                mode=PTMSession.Mode.IN_PERSON,
                location_or_url="Senior Block - Rooms 101 & 102",
                level=self.level,
                section=self.section,
                status=PTMSession.Status.DRAFT,
            )
            session.teachers.add(self.teacher_1, self.teacher_2)

            created_count = generate_slots_for_session(session)
            # 60 min / 15 min = 4 slots * 2 teachers = 8 slots
            self.assertEqual(created_count, 8)
            self.assertEqual(session.slots.count(), 8)

            # Test idempotency: generating again adds 0 new slots
            recreated_count = generate_slots_for_session(session)
            self.assertEqual(recreated_count, 0)
            self.assertEqual(session.slots.count(), 8)

    def test_slot_booking_and_double_booking_prevention(self):
        """Test atomic slot booking and verification that double bookings are blocked."""
        with tenant_context(self.school):
            session = PTMSession.objects.create(
                title="Term 1 Mid-Term PTM",
                academic_year=self.ay,
                meeting_date=FUTURE,
                start_time=datetime.time(9, 0),
                end_time=datetime.time(10, 0),
                slot_duration_minutes=15,
                status=PTMSession.Status.PUBLISHED,
            )
            session.teachers.add(self.teacher_1, self.teacher_2)
            generate_slots_for_session(session)

            # Slot 1: Teacher 1 at 09:00 - 09:15
            t1_slot_900 = session.slots.get(teacher=self.teacher_1, start_time=datetime.time(9, 0))
            # Slot 2: Teacher 2 at 09:00 - 09:15
            t2_slot_900 = session.slots.get(teacher=self.teacher_2, start_time=datetime.time(9, 0))
            # Slot 3: Teacher 1 at 09:15 - 09:30
            t1_slot_915 = session.slots.get(teacher=self.teacher_1, start_time=datetime.time(9, 15))

            # 1. Parent 1 books t1_slot_900 for Student 1
            booked = book_slot(
                slot_id=t1_slot_900.id,
                student=self.student_1,
                parent=self.parent_1,
                notes="Discuss math mid-term test paper",
            )
            self.assertEqual(booked.status, PTMSlot.Status.BOOKED)
            self.assertEqual(booked.student, self.student_1)
            self.assertEqual(booked.parent_notes, "Discuss math mid-term test paper")

            # 2. Parent 2 attempts to book the already-booked slot -> must fail
            with self.assertRaises(ValidationError) as ctx:
                book_slot(
                    slot_id=t1_slot_900.id,
                    student=self.student_2,
                    parent=self.parent_2,
                )
            self.assertIn("already been booked", str(ctx.exception))

            # 3. Parent 1 attempts to book a second slot with the SAME teacher in the SAME session -> must fail
            with self.assertRaises(ValidationError) as ctx:
                book_slot(
                    slot_id=t1_slot_915.id,
                    student=self.student_1,
                    parent=self.parent_1,
                )
            self.assertIn("already booked for this student", str(ctx.exception))

            # 4. Parent 1 attempts to book Teacher 2 at the SAME TIME (09:00) -> must fail (time clash)
            with self.assertRaises(ValidationError) as ctx:
                book_slot(
                    slot_id=t2_slot_900.id,
                    student=self.student_1,
                    parent=self.parent_1,
                )
            self.assertIn("already has another meeting booked at this exact time", str(ctx.exception))

    def test_slot_cancellation_workflow(self):
        """Parent can cancel their own booking; other parents cannot cancel it."""
        with tenant_context(self.school):
            session = PTMSession.objects.create(
                title="Annual PTM",
                academic_year=self.ay,
                meeting_date=FUTURE,
                start_time=datetime.time(9, 0),
                end_time=datetime.time(10, 0),
                slot_duration_minutes=15,
                status=PTMSession.Status.PUBLISHED,
            )
            session.teachers.add(self.teacher_1)
            generate_slots_for_session(session)

            slot = session.slots.first()
            book_slot(slot.id, self.student_1, self.parent_1, "Notes")

            # Parent 2 tries to cancel Parent 1's booking -> PermissionDenied
            with self.assertRaises(PermissionDenied):
                cancel_booking(slot.id, parent=self.parent_2, is_admin=False)

            # Parent 1 cancels their own booking -> Success
            cancelled = cancel_booking(slot.id, parent=self.parent_1, is_admin=False)
            self.assertEqual(cancelled.status, PTMSlot.Status.AVAILABLE)
            self.assertIsNone(cancelled.student)
            self.assertIsNone(cancelled.booked_by_parent)

    def test_teacher_blocking_and_feedback(self):
        """Teacher can block slots and record post-meeting notes & attendance."""
        with tenant_context(self.school):
            session = PTMSession.objects.create(
                title="Term 2 PTM",
                academic_year=self.ay,
                meeting_date=FUTURE,
                start_time=datetime.time(9, 0),
                end_time=datetime.time(10, 0),
                slot_duration_minutes=15,
                status=PTMSession.Status.PUBLISHED,
            )
            session.teachers.add(self.teacher_1)
            generate_slots_for_session(session)

            slot = session.slots.first()
            # Block slot
            blocked = block_slot(slot.id, teacher_member=self.teacher_1)
            self.assertEqual(blocked.status, PTMSlot.Status.BLOCKED)

            # Unblock slot
            unblocked = unblock_slot(slot.id, teacher_member=self.teacher_1)
            self.assertEqual(unblocked.status, PTMSlot.Status.AVAILABLE)

            # Book slot then record feedback
            book_slot(slot.id, self.student_1, self.parent_1)
            feedback_slot = record_slot_feedback(
                slot_id=slot.id,
                teacher_member=self.teacher_1,
                feedback="Student shows good grasp of algebra. Recommended 20 mins extra geometry practice.",
                attended=True,
            )
            self.assertEqual(feedback_slot.status, PTMSlot.Status.COMPLETED)
            self.assertTrue(feedback_slot.attended)
            self.assertIn("algebra", feedback_slot.teacher_feedback)

    def test_parent_portal_ptm_endpoints(self):
        """Parent views applicable sessions, available slots, books, and views active bookings."""
        with tenant_context(self.school):
            session = PTMSession.objects.create(
                title="Term 1 Mid-Term PTM",
                academic_year=self.ay,
                meeting_date=FUTURE,
                start_time=datetime.time(9, 0),
                end_time=datetime.time(10, 0),
                slot_duration_minutes=15,
                mode=PTMSession.Mode.IN_PERSON,
                location_or_url="Room 101",
                level=self.level,
                status=PTMSession.Status.PUBLISHED,
            )
            session.teachers.add(self.teacher_1)
            generate_slots_for_session(session)

            # 1. Parent views sessions
            request = self.factory.get("/api/ptm/parent/sessions/")
            request.tenant = self.school
            force_authenticate(request, user=self.p1_user)
            response = ParentPTMSessionsView.as_view()(request)
            self.assertEqual(response.status_code, 200, response.data)
            self.assertEqual(len(response.data), 1)
            self.assertEqual(response.data[0]["title"], "Term 1 Mid-Term PTM")

            # 2. Parent views available slots for child
            request = self.factory.get(
                f"/api/ptm/parent/available-slots/?session_id={session.id}&student_id={self.student_1.id}"
            )
            request.tenant = self.school
            force_authenticate(request, user=self.p1_user)
            response = ParentAvailableSlotsView.as_view()(request)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(len(response.data["slots"]), 4)

            # 3. Parent books slot
            slot_to_book = response.data["slots"][0]
            request = self.factory.post(
                "/api/ptm/parent/book/",
                {
                    "slot_id": slot_to_book["id"],
                    "student_id": str(self.student_1.id),
                    "notes": "Discuss quarterly progress",
                },
                format="json",
            )
            request.tenant = self.school
            force_authenticate(request, user=self.p1_user)
            response = ParentBookSlotView.as_view()(request)
            self.assertEqual(response.status_code, 201)

            # 4. Parent views their bookings
            request = self.factory.get("/api/ptm/parent/my-bookings/")
            request.tenant = self.school
            force_authenticate(request, user=self.p1_user)
            response = ParentMyBookingsView.as_view()(request)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(len(response.data), 1)
            self.assertEqual(response.data[0]["student_detail"]["enrollment_id"], "STU-001")

    def test_slot_endpoints_are_limited_to_ptm_staff(self):
        """A login is not enough: parents and students see no slots and change none, a teacher manages only
        their own, and a school owner (who holds manage_ptm through the owner role) manages anyone's."""
        with tenant_context(self.school):
            session = PTMSession.objects.create(
                title="Access PTM", academic_year=self.ay, meeting_date=FUTURE,
                start_time=datetime.time(9, 0), end_time=datetime.time(10, 0), slot_duration_minutes=15,
                status=PTMSession.Status.PUBLISHED,
            )
            session.teachers.add(self.teacher_1, self.teacher_2)
            generate_slots_for_session(session)
            slot_of_1 = session.slots.filter(teacher=self.teacher_1).first()
            slot_of_2 = session.slots.filter(teacher=self.teacher_2).first()
            teacher_1_user = User.objects.get(id=self.teacher_1.profile.user_id)

            def call(user, action, slot):
                method = "get" if action == "list" else "post"
                request = getattr(self.factory, method)(f"/api/ptm/slots/{slot.id}/{action}/")
                request.tenant = self.school
                force_authenticate(request, user=user)
                if action == "list":
                    return PTMSlotViewSet.as_view({"get": "list"})(request)
                return PTMSlotViewSet.as_view({"post": action})(request, pk=str(slot.id))

            # No staff or admin role: no listing, no blocking.
            self.assertEqual(call(self.p1_user, "list", slot_of_1).status_code, 403)
            self.assertEqual(call(self.p1_user, "block", slot_of_1).status_code, 403)
            slot_of_1.refresh_from_db()
            self.assertEqual(slot_of_1.status, PTMSlot.Status.AVAILABLE)

            # A teacher blocks their own slot but not a colleague's.
            self.assertEqual(call(teacher_1_user, "block", slot_of_1).status_code, 200)
            self.assertEqual(call(teacher_1_user, "block", slot_of_2).status_code, 400)
            slot_of_2.refresh_from_db()
            self.assertEqual(slot_of_2.status, PTMSlot.Status.AVAILABLE)

            # The owner is not a teacher, yet may unblock and block any slot.
            self.assertEqual(call(self.owner_user, "unblock", slot_of_1).status_code, 200)
            self.assertEqual(call(self.owner_user, "block", slot_of_2).status_code, 200)

    def test_booking_rules_for_parents(self):
        """Past sessions, other classes' sessions and a switched-off parent permission are all refused."""
        from django.core.exceptions import ValidationError as DjangoValidationError

        from roles.models import Permission

        with tenant_context(self.school):
            def make(**extra):
                session = PTMSession.objects.create(
                    title="Rules PTM", academic_year=self.ay, start_time=datetime.time(9, 0),
                    end_time=datetime.time(9, 30), slot_duration_minutes=15,
                    status=PTMSession.Status.PUBLISHED, **extra,
                )
                session.teachers.add(self.teacher_1)
                generate_slots_for_session(session)
                return session

            past = make(meeting_date=datetime.date.today() - datetime.timedelta(days=3))
            with self.assertRaises(DjangoValidationError):
                book_slot(past.slots.first().id, self.student_1, self.parent_1)

            other_level = AcademicLevel.objects.create(program=self.program, name="Grade 9", order=9)
            elsewhere = make(meeting_date=FUTURE, level=other_level)
            with self.assertRaises(DjangoValidationError):
                book_slot(elsewhere.slots.first().id, self.student_1, self.parent_1)

            own_class = make(meeting_date=FUTURE, level=self.level)
            booked = book_slot(own_class.slots.first().id, self.student_1, self.parent_1)
            self.assertEqual(booked.status, PTMSlot.Status.BOOKED)

            # Without the permission the parent endpoints are closed, even for a real parent.
            parent_role = Role.objects.get(slug="parent")
            parent_role.permissions.remove(Permission.objects.get(codename="view_child_ptm"))
            request = self.factory.get("/api/ptm/parent/sessions/")
            request.tenant = self.school
            force_authenticate(request, user=self.p1_user)
            self.assertEqual(ParentPTMSessionsView.as_view()(request).status_code, 403)
