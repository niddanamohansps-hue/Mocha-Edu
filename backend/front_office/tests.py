import datetime
import uuid as uuid_module

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TransactionTestCase
from django.utils import timezone
from django_tenants.utils import tenant_context
from rest_framework.test import APIRequestFactory, force_authenticate

from academics.models import AcademicYear, AcademicLevel, Section
from organizations.models import Domain, Organization
from profiles.models import Profile
from roles.models import Role, UserRole
from roles.signals import seed_default_roles
from staff.models import StaffMember
from students.models import Student, StudentLevel

from .models import VisitorLog, StudentGatePass, PostalRecord
from .serializers import VisitorLogSerializer, StudentGatePassSerializer, PostalRecordSerializer
from .services import (
    generate_visitor_pass_number,
    generate_gate_pass_number,
    get_front_office_overview,
)
from .views import (
    VisitorLogViewSet,
    StudentGatePassViewSet,
    PostalRecordViewSet,
    FrontOfficeOverviewView,
)

User = get_user_model()


class FrontOfficeFixtureMixin:
    def _build_school(self, schema_name=None, domain=None, name="Front Office Test School"):
        suffix = uuid_module.uuid4().hex[:8]
        schema_name = schema_name or f"fo_{suffix}"
        domain = domain or f"fo-{suffix}.localhost"
        connection.set_schema_to_public()
        school = Organization.objects.create(schema_name=schema_name, name=name)
        Domain.objects.create(domain=domain, tenant=school, is_primary=True)
        return school


class FrontOfficeIntegrationTest(FrontOfficeFixtureMixin, TransactionTestCase):
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

            # Create an Owner user
            self.owner_user = User.objects.create_user(
                username=f"owner_{uuid_module.uuid4().hex[:6]}@school.com",
                email="owner@school.com",
                password="OwnerPassword123!",
            )
            owner_role = Role.objects.get(slug="owner")
            UserRole.objects.create(user=self.owner_user, role=owner_role)

            # Create unprivileged user
            self.plain_user = User.objects.create_user(
                username=f"staff_{uuid_module.uuid4().hex[:6]}@school.com",
                email="staff@school.com",
                password="StaffPassword123!",
            )

            # Create sample Staff member
            self.staff_profile = Profile.objects.create(
                first_name="Ramesh",
                last_name="Verma",
                email=f"ramesh_{uuid_module.uuid4().hex[:4]}@school.com",
                phone="9876543210",
                date_of_birth=datetime.date(1985, 5, 20),
            )
            self.staff_member = StaffMember.objects.create(
                profile=self.staff_profile,
                employee_id=f"EMP-{uuid_module.uuid4().hex[:4].upper()}",
                joining_date=datetime.date(2020, 6, 1),
                designation="Vice Principal",
            )

            # Create sample Student
            self.student_profile = Profile.objects.create(
                first_name="Ananya",
                last_name="Singh",
                date_of_birth=datetime.date(2012, 8, 14),
                gender="female",
            )
            self.student = Student.objects.create(
                profile=self.student_profile,
                enrollment_id=f"ADM-{uuid_module.uuid4().hex[:4].upper()}",
                admission_date=datetime.date(2022, 4, 1),
                status="active",
            )

    def test_visitor_checkin_and_auto_numbering(self):
        with tenant_context(self.school):
            v_num = generate_visitor_pass_number()
            self.assertTrue(v_num.startswith("VIS-"))

            # Create visitor via serializer
            data = {
                "visitor_name": "Suresh Gupta",
                "phone": "9811223344",
                "id_proof_type": "aadhaar",
                "id_proof_number": "123456789012",
                "organization": "Gupta Book Distributors",
                "purpose": "vendor_delivery",
                "purpose_details": "Delivering library books",
                "badge_number": "V-01",
                "vehicle_number": "DL-01-AB-1234",
                "number_of_visitors": 2,
            }
            serializer = VisitorLogSerializer(data=data)
            self.assertTrue(serializer.is_valid(), serializer.errors)
            vis = serializer.save()

            self.assertEqual(vis.visitor_name, "Suresh Gupta")
            self.assertEqual(vis.status, VisitorLog.Status.ACTIVE)
            self.assertEqual(vis.badge_number, "V-01")
            self.assertTrue(vis.pass_number.startswith("VIS-"))
            self.assertIsNone(vis.check_out_time)

    def test_visitor_checkout(self):
        with tenant_context(self.school):
            vis = VisitorLog.objects.create(
                pass_number="VIS-2026-0099",
                visitor_name="Meena Devi",
                phone="9876500000",
                purpose=VisitorLog.Purpose.PARENT_MEETING,
                status=VisitorLog.Status.ACTIVE,
            )

            view = VisitorLogViewSet.as_view({"post": "check_out"})
            req = self.factory.post(
                f"/api/front-office/visitors/{vis.id}/check_out/",
                {"remarks": "Meeting finished with Class Teacher"},
            )
            req.tenant = self.school
            force_authenticate(req, user=self.owner_user)

            resp = view(req, pk=str(vis.id))
            self.assertEqual(resp.status_code, 200)

            vis.refresh_from_db()
            self.assertEqual(vis.status, VisitorLog.Status.CHECKED_OUT)
            self.assertIsNotNone(vis.check_out_time)
            self.assertIn("Exit note: Meeting finished", vis.remarks)

            # Re-checkout fails
            resp_repeat = view(req, pk=str(vis.id))
            self.assertEqual(resp_repeat.status_code, 400)

    def test_student_gate_pass_issuance_and_exit(self):
        with tenant_context(self.school):
            gp_num = generate_gate_pass_number()
            self.assertTrue(gp_num.startswith("GP-"))

            # Create gate pass
            data = {
                "student": str(self.student.id),
                "reason_category": "illness",
                "reason_details": "Student has high fever and headache since 11:30 AM",
                "picked_up_by_name": "Rajesh Singh",
                "relationship": "father",
                "picked_up_by_phone": "9811002200",
                "authorized_by_staff": str(self.staff_member.id),
            }
            serializer = StudentGatePassSerializer(data=data)
            self.assertTrue(serializer.is_valid(), serializer.errors)
            gp = serializer.save()

            self.assertEqual(gp.status, StudentGatePass.Status.ISSUED)
            self.assertEqual(gp.picked_up_by_name, "Rajesh Singh")
            self.assertTrue(gp.pass_number.startswith("GP-"))
            self.assertIsNone(gp.actual_exit_time)

            # Security Guard confirms departure at main gate
            view_exit = StudentGatePassViewSet.as_view({"post": "confirm_exit"})
            req_exit = self.factory.post(
                f"/api/front-office/gate-passes/{gp.id}/confirm_exit/",
                {"gate_security_note": "Father showed Aadhaar Card, exited in Car DL-04-9988"},
            )
            req_exit.tenant = self.school
            force_authenticate(req_exit, user=self.owner_user)

            resp_exit = view_exit(req_exit, pk=str(gp.id))
            self.assertEqual(resp_exit.status_code, 200)

            gp.refresh_from_db()
            self.assertEqual(gp.status, StudentGatePass.Status.DEPARTED)
            self.assertIsNotNone(gp.actual_exit_time)
            self.assertIn("Father showed Aadhaar Card", gp.gate_security_note)

    def test_postal_inward_outward_dispatch(self):
        with tenant_context(self.school):
            # Inward
            p_in = PostalRecord.objects.create(
                tracking_number="ED987654321IN",
                record_type=PostalRecord.RecordType.INWARD,
                title="CBSE Affiliation Inspection Report",
                from_title="Regional Office CBSE, Delhi",
                to_title="Principal Office",
                courier_company="India Post Speed Post",
                recipient_staff=self.staff_member,
            )
            self.assertEqual(p_in.record_type, PostalRecord.RecordType.INWARD)

            # Outward
            p_out = PostalRecord.objects.create(
                tracking_number="DTDC11223344",
                record_type=PostalRecord.RecordType.OUTWARD,
                title="Student Transfer Certificate Documents",
                from_title="Admin Office",
                to_title="Kendriya Vidyalaya, Jaipur",
                courier_company="DTDC",
            )
            self.assertEqual(p_out.record_type, PostalRecord.RecordType.OUTWARD)

            # ViewSet query filtering
            view = PostalRecordViewSet.as_view({"get": "list"})
            req = self.factory.get("/api/front-office/postal/?record_type=inward")
            req.tenant = self.school
            force_authenticate(req, user=self.owner_user)

            resp = view(req)
            self.assertEqual(resp.status_code, 200)
            items = resp.data if isinstance(resp.data, list) else resp.data.get("results", [])
            self.assertEqual(len(items), 1)
            self.assertEqual(items[0]["tracking_number"], "ED987654321IN")

    def test_front_office_overview_stats(self):
        with tenant_context(self.school):
            today = timezone.localdate()

            # Active visitor
            VisitorLog.objects.create(
                pass_number="VIS-2026-0501",
                visitor_name="Vendor 1",
                phone="9999900001",
                status=VisitorLog.Status.ACTIVE,
            )
            # Checked out visitor
            VisitorLog.objects.create(
                pass_number="VIS-2026-0502",
                visitor_name="Parent 2",
                phone="9999900002",
                status=VisitorLog.Status.CHECKED_OUT,
            )

            # Active Gate pass today
            StudentGatePass.objects.create(
                pass_number="GP-2026-0501",
                student=self.student,
                departure_date=today,
                picked_up_by_name="Mother",
                picked_up_by_phone="9999900003",
                status=StudentGatePass.Status.ISSUED,
            )

            stats = get_front_office_overview()
            self.assertEqual(stats["active_visitors_inside"], 1)
            self.assertEqual(stats["visitors_today"], 2)
            self.assertEqual(stats["gate_passes_today"], 1)
            self.assertEqual(stats["active_gate_passes"], 1)

    def test_front_office_permissions_enforcement(self):
        with tenant_context(self.school):
            # Plain user without manage_visitors should get 403 on visitor creation
            view_v = VisitorLogViewSet.as_view({"post": "create"})
            req_v = self.factory.post(
                "/api/front-office/visitors/",
                {"visitor_name": "Test Visitor", "phone": "9000000000"},
            )
            req_v.tenant = self.school
            force_authenticate(req_v, user=self.plain_user)

            resp_v = view_v(req_v)
            self.assertEqual(resp_v.status_code, 403)

            # Owner succeeds
            req_v_owner = self.factory.post(
                "/api/front-office/visitors/",
                {"visitor_name": "Authorized Visitor", "phone": "9000000001"},
            )
            req_v_owner.tenant = self.school
            force_authenticate(req_v_owner, user=self.owner_user)

            resp_v_owner = view_v(req_v_owner)
            self.assertEqual(resp_v_owner.status_code, 201)
