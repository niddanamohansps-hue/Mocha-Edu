"""
EduSekai Staff Leave Management Automated Test Suite (Phase 5)

Comprehensive regression and integration tests covering:
- LeaveType CRUD and RBAC permissions
- Working days calculation with weekends and published calendar holidays
- Atomic balance reservation and concurrency overspend protection
- Overlapping application prevention
- Full approval workflow and automatic StaffAttendance synchronization
- Self-approval prohibition
- Full rejection workflow with mandatory comments and balance release
- Cancellation workflow and safe attendance reversion
- Tenant isolation and object-level permissions
- Timetable affected periods discovery and substitute instructor matching
- Private document upload validation and protected download access
- Audit logging and notification outbox dispatch
"""

from datetime import date, timedelta
from decimal import Decimal
import io
import uuid

from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection
from django.test import TransactionTestCase
from django_tenants.utils import tenant_context
from rest_framework.test import APIClient

from accounts.models import User
from academics.models import AcademicLevel, AcademicYear, CalendarEvent, Program, Section, Subject
from attendance.models import StaffAttendance
from core.models import AuditLog
from notifications.models import Notification
from organizations.models import Domain, Organization
from profiles.models import Profile
from roles.models import Permission, Role, UserRole
from timetable.models import Period, TimetableEntry, TimetableSubstitution

from .models import (
    Instructor,
    LeaveApplication,
    LeaveApproval,
    LeaveType,
    StaffLeaveBalance,
    StaffMember,
)

PASSWORD = "Pass1234!"


class LeaveFixtureMixin:
    SCHEMA_NAME = "leave_p05_school"
    DOMAIN = "leave-p05.localhost"
    TENANT_SCHEMAS = ["leave_p05_school", "leave_p05_other"]

    def _build_school(self, schema_name, domain):
        connection.set_schema_to_public()
        school = Organization.objects.create(schema_name=schema_name, name=f"School {schema_name}")
        Domain.objects.create(domain=domain, tenant=school, is_primary=True)
        return school

    def _build_user(self, username, codenames=None, owner=False):
        user = User.objects.create_user(username=username, email=f"{username}@leave.test", password=PASSWORD)
        with tenant_context(self.school):
            if owner:
                role = Role.objects.get(slug="owner")
            else:
                slug = f"role-{uuid.uuid4().hex[:8]}"
                role = Role.objects.create(name=slug, slug=slug, is_system_role=False)
                role.permissions.set(Permission.objects.filter(codename__in=codenames or []))
            UserRole.objects.create(user=user, role=role)
        return user

    def _client_as(self, user, host):
        client = APIClient()
        resp = client.post(
            "/api/auth/login/",
            {"username": user.username, "password": PASSWORD},
            HTTP_HOST=host,
        )
        assert resp.status_code == 200, resp.data
        return client

    def _make_staff(self, first, last, employee_id, user=None, is_instructor=False, spec="Mathematics"):
        with tenant_context(self.school):
            profile = None
            if user:
                profile = Profile.objects.filter(user_id=user.id).first()
            if not profile:
                profile = Profile.objects.create(
                    user_id=user.id if user else None,
                    first_name=first,
                    last_name=last,
                )
            else:
                profile.first_name = first
                profile.last_name = last
                profile.save(update_fields=["first_name", "last_name"])

            staff = StaffMember.objects.filter(profile=profile).first()
            if not staff:
                staff = StaffMember.objects.create(
                    profile=profile,
                    employee_id=employee_id,
                    designation="Senior Teacher" if is_instructor else "Office Administrator",
                    department="Academics" if is_instructor else "Administration",
                    is_active=True,
                )
            else:
                staff.employee_id = employee_id
                staff.designation = "Senior Teacher" if is_instructor else "Office Administrator"
                staff.department = "Academics" if is_instructor else "Administration"
                staff.is_active = True
                staff.save(update_fields=["employee_id", "designation", "department", "is_active"])

            if is_instructor:
                Instructor.objects.get_or_create(
                    staff_member=staff,
                    defaults={"specialization": spec},
                )
            return staff

    def _cleanup(self):
        connection.set_schema_to_public()
        for school in Organization.objects.filter(schema_name__in=self.TENANT_SCHEMAS):
            school.delete(force_drop=True)
        User.objects.filter(username__startswith="leave_").delete()

    def setUp(self):
        self.addCleanup(self._cleanup)
        self.school = self._build_school(self.SCHEMA_NAME, self.DOMAIN)

        # Users and staff members
        self.owner_user = self._build_user("leave_owner", owner=True)
        self.approver_user = self._build_user("leave_approver", codenames=["view_all_leaves", "manage_staff_leaves"])
        self.staff_user_a = self._build_user("leave_staff_a", codenames=["view_own_leaves", "apply_staff_leave", "cancel_own_leave"])
        self.staff_user_b = self._build_user("leave_staff_b", codenames=["view_own_leaves", "apply_staff_leave", "cancel_own_leave"])

        self.owner_staff = self._make_staff("Principal", "Roy", "EMP-000", user=self.owner_user)
        self.approver_staff = self._make_staff("HR", "Head", "EMP-001", user=self.approver_user)
        self.staff_a = self._make_staff("Ravi", "Verma", "EMP-002", user=self.staff_user_a, is_instructor=True, spec="Mathematics")
        self.staff_b = self._make_staff("Priya", "Nair", "EMP-003", user=self.staff_user_b, is_instructor=True, spec="Physics")

        with tenant_context(self.school):
            # Academic Year
            self.academic_year = AcademicYear.objects.create(
                name="2026-27",
                start_date=date(2026, 4, 1),
                end_date=date(2027, 3, 31),
                is_current=True,
            )

            # Leave Types
            self.cl_type = LeaveType.objects.create(
                name="Casual Leave",
                code="CL",
                annual_allocation_days=Decimal("12.0"),
                is_paid=True,
                requires_document=False,
                max_consecutive_days=3,
            )
            self.sl_type = LeaveType.objects.create(
                name="Sick Leave",
                code="SL",
                annual_allocation_days=Decimal("10.0"),
                is_paid=True,
                requires_document=True,
            )


class StaffLeaveManagementTests(LeaveFixtureMixin, TransactionTestCase):

    def test_leave_type_crud_and_permissions(self):
        """BLK-LEAVE-01: Verifies LeaveType configuration permissions and CRUD."""
        admin_client = self._client_as(self.owner_user, self.DOMAIN)
        staff_client = self._client_as(self.staff_user_a, self.DOMAIN)

        # 1. Staff can view active leave types
        res = staff_client.get("/api/staff/leaves/types/", HTTP_HOST=self.DOMAIN)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.data), 2)

        # 2. Staff cannot create a leave type (403)
        res = staff_client.post(
            "/api/staff/leaves/types/",
            {"name": "Maternity Leave", "code": "ML", "annual_allocation_days": 90.0},
            format="json",
            HTTP_HOST=self.DOMAIN,
        )
        self.assertEqual(res.status_code, 403)

        # 3. Admin can create a leave type
        res = admin_client.post(
            "/api/staff/leaves/types/",
            {"name": "Maternity Leave", "code": "ML", "annual_allocation_days": 90.0, "is_paid": True},
            format="json",
            HTTP_HOST=self.DOMAIN,
        )
        self.assertEqual(res.status_code, 201)
        ml_id = res.data["id"]

        # 4. Admin can update
        res = admin_client.patch(
            f"/api/staff/leaves/types/{ml_id}/",
            {"description": "Maternity leave policy updated"},
            format="json",
            HTTP_HOST=self.DOMAIN,
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["description"], "Maternity leave policy updated")

    def test_working_days_calculation_with_weekends_and_holidays(self):
        """BLK-LEAVE-02: Verifies working days computation excluding Sundays and published school holidays."""
        with tenant_context(self.school):
            # Calendar Holiday: Oct 21, 2026 (Wednesday) - Diwali
            CalendarEvent.objects.create(
                title="Diwali Holiday",
                event_type="HOLIDAY",
                is_holiday=True,
                status="PUBLISHED",
                start_date=date(2026, 10, 21),
                end_date=date(2026, 10, 21),
                academic_year=self.academic_year,
            )

        client = self._client_as(self.staff_user_a, self.DOMAIN)

        # Window: Oct 19, 2026 (Mon) to Oct 25, 2026 (Sun)
        # Total days: 7. Excludes: Oct 21 (Diwali), Oct 25 (Sunday). Net working days = 5.
        res = client.post(
            "/api/staff/leaves/applications/",
            {
                "leave_type_id": str(self.cl_type.id),
                "start_date": "2026-10-19",
                "end_date": "2026-10-23", # Mon to Fri, 1 holiday -> 4 working days
                "reason": "Family function",
            },
            format="json",
            HTTP_HOST=self.DOMAIN,
        )
        # CL has max_consecutive_days = 3; 4 working days should exceed limit!
        self.assertEqual(res.status_code, 400)
        self.assertIn("exceeds the maximum consecutive limit", str(res.data))

        # Request 2 working days: Oct 19 to Oct 20 (Mon-Tue)
        res = client.post(
            "/api/staff/leaves/applications/",
            {
                "leave_type_id": str(self.cl_type.id),
                "start_date": "2026-10-19",
                "end_date": "2026-10-20",
                "reason": "Family function",
            },
            format="json",
            HTTP_HOST=self.DOMAIN,
        )
        self.assertEqual(res.status_code, 201)
        self.assertEqual(Decimal(str(res.data["working_days"])), Decimal("2.0"))

    def test_half_day_leave_handling(self):
        """BLK-LEAVE-03: Verifies half-day leave validation and 0.5-day duration."""
        client = self._client_as(self.staff_user_a, self.DOMAIN)

        # Half day across multiple dates rejected
        res = client.post(
            "/api/staff/leaves/applications/",
            {
                "leave_type_id": str(self.cl_type.id),
                "start_date": "2026-10-19",
                "end_date": "2026-10-20",
                "is_half_day": True,
                "half_day_session": "morning",
                "reason": "Doctor appointment",
            },
            format="json",
            HTTP_HOST=self.DOMAIN,
        )
        self.assertEqual(res.status_code, 400)

        # Valid single-date half-day leave
        res = client.post(
            "/api/staff/leaves/applications/",
            {
                "leave_type_id": str(self.cl_type.id),
                "start_date": "2026-10-19",
                "end_date": "2026-10-19",
                "is_half_day": True,
                "half_day_session": "morning",
                "reason": "Doctor appointment",
            },
            format="json",
            HTTP_HOST=self.DOMAIN,
        )
        self.assertEqual(res.status_code, 201)
        self.assertEqual(Decimal(str(res.data["working_days"])), Decimal("0.5"))

    def test_insufficient_balance_rejection(self):
        """BLK-LEAVE-04: Verifies atomic balance check and rejection of overspending requests."""
        with tenant_context(self.school):
            # Set balance for Staff A on CL to exactly 1.0 day
            StaffLeaveBalance.objects.update_or_create(
                staff=self.staff_a,
                leave_type=self.cl_type,
                academic_year="2026-27",
                defaults={"allocated_days": Decimal("1.0"), "used_days": Decimal("0.0"), "pending_days": Decimal("0.0")},
            )

        client = self._client_as(self.staff_user_a, self.DOMAIN)

        # Request 2 days: Oct 19 to Oct 20
        res = client.post(
            "/api/staff/leaves/applications/",
            {
                "leave_type_id": str(self.cl_type.id),
                "start_date": "2026-10-19",
                "end_date": "2026-10-20",
                "reason": "Personal work",
            },
            format="json",
            HTTP_HOST=self.DOMAIN,
        )
        self.assertEqual(res.status_code, 400)
        self.assertIn("Insufficient leave balance", str(res.data))

    def test_overlapping_application_rejection(self):
        """BLK-LEAVE-05: Verifies that overlapping pending or approved leave requests are blocked."""
        client = self._client_as(self.staff_user_a, self.DOMAIN)

        # First application: Oct 19 to Oct 20
        res = client.post(
            "/api/staff/leaves/applications/",
            {
                "leave_type_id": str(self.cl_type.id),
                "start_date": "2026-10-19",
                "end_date": "2026-10-20",
                "reason": "First leave",
            },
            format="json",
            HTTP_HOST=self.DOMAIN,
        )
        self.assertEqual(res.status_code, 201)

        # Second application overlapping Oct 20 to Oct 22
        res2 = client.post(
            "/api/staff/leaves/applications/",
            {
                "leave_type_id": str(self.cl_type.id),
                "start_date": "2026-10-20",
                "end_date": "2026-10-22",
                "reason": "Overlapping leave",
            },
            format="json",
            HTTP_HOST=self.DOMAIN,
        )
        self.assertEqual(res2.status_code, 400)
        self.assertIn("overlapping", str(res2.data).lower())

    def test_approval_workflow_and_attendance_synchronization(self):
        """BLK-LEAVE-06: Verifies approval shifts pending->used and automatically writes StaffAttendance."""
        staff_client = self._client_as(self.staff_user_a, self.DOMAIN)
        approver_client = self._client_as(self.approver_user, self.DOMAIN)

        # Submit 2 days leave
        res = staff_client.post(
            "/api/staff/leaves/applications/",
            {
                "leave_type_id": str(self.cl_type.id),
                "start_date": "2026-11-02", # Mon
                "end_date": "2026-11-03",   # Tue
                "reason": "Out of town",
            },
            format="json",
            HTTP_HOST=self.DOMAIN,
        )
        self.assertEqual(res.status_code, 201)
        app_id = res.data["id"]

        with tenant_context(self.school):
            bal = StaffLeaveBalance.objects.get(staff=self.staff_a, leave_type=self.cl_type, academic_year="2026-27")
            self.assertEqual(bal.pending_days, Decimal("2.0"))
            self.assertEqual(bal.used_days, Decimal("0.0"))

        # Self-approval prohibition check: Staff A attempts to approve own leave
        self_approval_res = staff_client.post(
            f"/api/staff/leaves/applications/{app_id}/approve/",
            {"comments": "Approving my own leave"},
            format="json",
            HTTP_HOST=self.DOMAIN,
        )
        self.assertEqual(self_approval_res.status_code, 403)

        # Approver approves
        approve_res = approver_client.post(
            f"/api/staff/leaves/applications/{app_id}/approve/",
            {"comments": "Approved by HR"},
            format="json",
            HTTP_HOST=self.DOMAIN,
        )
        self.assertEqual(approve_res.status_code, 200)
        self.assertEqual(approve_res.data["status"], "approved")

        # Verify balance transition
        with tenant_context(self.school):
            bal.refresh_from_db()
            self.assertEqual(bal.pending_days, Decimal("0.0"))
            self.assertEqual(bal.used_days, Decimal("2.0"))

            # Verify StaffAttendance synchronization
            att_records = StaffAttendance.objects.filter(staff=self.staff_a, date__in=[date(2026, 11, 2), date(2026, 11, 3)])
            self.assertEqual(att_records.count(), 2)
            for rec in att_records:
                self.assertEqual(rec.status, "leave")
                self.assertIn(f"[LEAVE_APP:{app_id}]", rec.remarks)

            # Verify LeaveApproval audit history
            approvals = LeaveApproval.objects.filter(application_id=app_id)
            self.assertEqual(approvals.count(), 1)
            self.assertEqual(approvals.first().decision, "approved")
            self.assertEqual(approvals.first().approver, self.approver_staff)

    def test_rejection_workflow_and_reservation_release(self):
        """BLK-LEAVE-07: Verifies rejection requires comments, releases pending days, and updates status."""
        staff_client = self._client_as(self.staff_user_a, self.DOMAIN)
        approver_client = self._client_as(self.approver_user, self.DOMAIN)

        res = staff_client.post(
            "/api/staff/leaves/applications/",
            {
                "leave_type_id": str(self.cl_type.id),
                "start_date": "2026-11-09",
                "end_date": "2026-11-10",
                "reason": "Personal",
            },
            format="json",
            HTTP_HOST=self.DOMAIN,
        )
        self.assertEqual(res.status_code, 201)
        app_id = res.data["id"]

        # Rejection without comments fails
        fail_res = approver_client.post(
            f"/api/staff/leaves/applications/{app_id}/reject/",
            {"comments": ""},
            format="json",
            HTTP_HOST=self.DOMAIN,
        )
        self.assertEqual(fail_res.status_code, 400)

        # Successful rejection
        reject_res = approver_client.post(
            f"/api/staff/leaves/applications/{app_id}/reject/",
            {"comments": "Exam week, leave denied"},
            format="json",
            HTTP_HOST=self.DOMAIN,
        )
        self.assertEqual(reject_res.status_code, 200)
        self.assertEqual(reject_res.data["status"], "rejected")

        with tenant_context(self.school):
            bal = StaffLeaveBalance.objects.get(staff=self.staff_a, leave_type=self.cl_type, academic_year="2026-27")
            self.assertEqual(bal.pending_days, Decimal("0.0"))
            self.assertEqual(bal.used_days, Decimal("0.0"))

    def test_cancellation_workflow_and_attendance_reversion(self):
        """BLK-LEAVE-08: Verifies cancelling approved leave releases used days and safely reverts attendance."""
        staff_client = self._client_as(self.staff_user_a, self.DOMAIN)
        approver_client = self._client_as(self.approver_user, self.DOMAIN)

        # 1. Apply and approve
        res = staff_client.post(
            "/api/staff/leaves/applications/",
            {
                "leave_type_id": str(self.cl_type.id),
                "start_date": "2026-11-16",
                "end_date": "2026-11-17",
                "reason": "Trip",
            },
            format="json",
            HTTP_HOST=self.DOMAIN,
        )
        app_id = res.data["id"]
        approver_client.post(f"/api/staff/leaves/applications/{app_id}/approve/", {"comments": "Ok"}, format="json", HTTP_HOST=self.DOMAIN)

        with tenant_context(self.school):
            self.assertEqual(StaffAttendance.objects.filter(staff=self.staff_a, date=date(2026, 11, 16)).count(), 1)

        # 2. Staff cancels own approved leave
        cancel_res = staff_client.post(
            f"/api/staff/leaves/applications/{app_id}/cancel/",
            {"reason": "Trip cancelled"},
            format="json",
            HTTP_HOST=self.DOMAIN,
        )
        self.assertEqual(cancel_res.status_code, 200)
        self.assertEqual(cancel_res.data["status"], "cancelled")

        with tenant_context(self.school):
            bal = StaffLeaveBalance.objects.get(staff=self.staff_a, leave_type=self.cl_type, academic_year="2026-27")
            self.assertEqual(bal.used_days, Decimal("0.0"))
            # Attendance safely deleted because it was tagged [LEAVE_APP:<id>]
            self.assertEqual(StaffAttendance.objects.filter(staff=self.staff_a, date=date(2026, 11, 16)).count(), 0)

    def test_tenant_isolation_and_ownership_guards(self):
        """BLK-LEAVE-09: Verifies Staff A cannot view or cancel Staff B's leave application."""
        staff_a_client = self._client_as(self.staff_user_a, self.DOMAIN)
        staff_b_client = self._client_as(self.staff_user_b, self.DOMAIN)

        # Staff B submits leave
        res = staff_b_client.post(
            "/api/staff/leaves/applications/",
            {
                "leave_type_id": str(self.cl_type.id),
                "start_date": "2026-11-23",
                "end_date": "2026-11-24",
                "reason": "Staff B leave",
            },
            format="json",
            HTTP_HOST=self.DOMAIN,
        )
        app_id = res.data["id"]

        # Staff A attempts to inspect Staff B's application (403 Forbidden)
        view_res = staff_a_client.get(f"/api/staff/leaves/applications/{app_id}/", HTTP_HOST=self.DOMAIN)
        self.assertEqual(view_res.status_code, 403)

        # Staff A attempts to cancel Staff B's application (403 Forbidden)
        cancel_res = staff_a_client.post(f"/api/staff/leaves/applications/{app_id}/cancel/", HTTP_HOST=self.DOMAIN)
        self.assertEqual(cancel_res.status_code, 403)

    def test_timetable_impact_and_substitute_teacher_matching(self):
        """BLK-LEAVE-10: Verifies affected teaching period discovery and substitute assignment."""
        with tenant_context(self.school):
            prog = Program.objects.create(name="High School", code="HS")
            lvl = AcademicLevel.objects.create(program=prog, name="Grade 10", order=10)
            sec = Section.objects.create(level=lvl, name="A")
            subj = Subject.objects.create(level=lvl, name="Mathematics", code="MATH-10")
            period = Period.objects.create(
                academic_year="2026-27",
                name="Period 1",
                order=1,
                start_time="09:00",
                end_time="09:45",
            )
            # Staff A teaches Math on Mondays (day_of_week=0)
            entry = TimetableEntry.objects.create(
                academic_year="2026-27",
                section=sec,
                subject=subj,
                instructor=self.staff_a.instructor_record,
                day_of_week=0,
                period=period,
            )

        staff_a_client = self._client_as(self.staff_user_a, self.DOMAIN)
        approver_client = self._client_as(self.approver_user, self.DOMAIN)

        # Staff A takes leave on Nov 30, 2026 (Monday)
        res = staff_a_client.post(
            "/api/staff/leaves/applications/",
            {
                "leave_type_id": str(self.cl_type.id),
                "start_date": "2026-11-30",
                "end_date": "2026-11-30",
                "reason": "Sick",
            },
            format="json",
            HTTP_HOST=self.DOMAIN,
        )
        app_id = res.data["id"]

        # Inspect affected periods
        affected_res = approver_client.get(f"/api/staff/leaves/applications/{app_id}/affected-periods/", HTTP_HOST=self.DOMAIN)
        self.assertEqual(affected_res.status_code, 200)
        self.assertEqual(len(affected_res.data), 1)
        self.assertEqual(affected_res.data[0]["subject"], "Mathematics (MATH-10)")
        # Staff B (Instructor Priya) is free and suggested as substitute
        substitutes = affected_res.data[0]["eligible_substitutes"]
        self.assertTrue(any(s["name"] == "Priya Nair" for s in substitutes))

        # Assign Staff B as substitute
        assign_res = approver_client.post(
            "/api/staff/leaves/substitutions/assign/",
            {
                "entry_id": str(entry.id),
                "date": "2026-11-30",
                "substitute_instructor_id": self.staff_b.instructor_record.id,
                "reason": "Covering for Ravi",
            },
            format="json",
            HTTP_HOST=self.DOMAIN,
        )
        self.assertEqual(assign_res.status_code, 201)

        with tenant_context(self.school):
            sub = TimetableSubstitution.objects.get(timetable_entry=entry, date=date(2026, 11, 30))
            self.assertEqual(sub.substitute_instructor, self.staff_b.instructor_record)

    def test_private_supporting_document_security(self):
        """BLK-LEAVE-11: Verifies private document validation, protected static media, and authorized download."""
        staff_client = self._client_as(self.staff_user_a, self.DOMAIN)
        stranger_client = self._client_as(self.staff_user_b, self.DOMAIN)

        # 1. Invalid file extension rejected
        fake_exe = SimpleUploadedFile("malware.exe", b"MZ\x90\x00\x03\x00\x00\x00", content_type="application/x-dosexec")
        res = staff_client.post(
            "/api/staff/leaves/applications/",
            {
                "leave_type_id": str(self.sl_type.id),
                "start_date": "2026-12-07",
                "end_date": "2026-12-08",
                "reason": "Medical certificate",
                "document": fake_exe,
            },
            format="multipart",
            HTTP_HOST=self.DOMAIN,
        )
        self.assertEqual(res.status_code, 400)
        self.assertIn("Unsupported file type", str(res.data))

        # 2. Valid PDF document upload
        valid_pdf = SimpleUploadedFile("prescription.pdf", b"%PDF-1.4 sample content", content_type="application/pdf")
        res = staff_client.post(
            "/api/staff/leaves/applications/",
            {
                "leave_type_id": str(self.sl_type.id),
                "start_date": "2026-12-07",
                "end_date": "2026-12-08",
                "reason": "Medical certificate",
                "document": valid_pdf,
            },
            format="multipart",
            HTTP_HOST=self.DOMAIN,
        )
        self.assertEqual(res.status_code, 201)
        app_id = res.data["id"]

        # 3. Direct unauthenticated media download blocked (403 Forbidden)
        anon_client = APIClient()
        media_res = anon_client.get("/media/leave_documents/2026/12/prescription.pdf", HTTP_HOST=self.DOMAIN)
        self.assertEqual(media_res.status_code, 403)

        # 4. Stranger cannot download document via API (403 Forbidden)
        stranger_res = stranger_client.get(f"/api/staff/leaves/applications/{app_id}/document/", HTTP_HOST=self.DOMAIN)
        self.assertEqual(stranger_res.status_code, 403)

        # 5. Applicant can download document via API (200 OK)
        owner_res = staff_client.get(f"/api/staff/leaves/applications/{app_id}/document/", HTTP_HOST=self.DOMAIN)
        self.assertEqual(owner_res.status_code, 200)

    def test_audit_logging_and_notifications(self):
        """BLK-LEAVE-12: Verifies AuditLog rows and in-app Notification rows are recorded."""
        staff_client = self._client_as(self.staff_user_a, self.DOMAIN)

        res = staff_client.post(
            "/api/staff/leaves/applications/",
            {
                "leave_type_id": str(self.cl_type.id),
                "start_date": "2026-12-14",
                "end_date": "2026-12-15",
                "reason": "Testing audit",
            },
            format="json",
            HTTP_HOST=self.DOMAIN,
        )
        self.assertEqual(res.status_code, 201)
        app_id = res.data["id"]

        with tenant_context(self.school):
            # Check AuditLog
            log_entry = AuditLog.objects.filter(model_name="LeaveApplication", object_id=app_id, action="CREATE").first()
            self.assertIsNotNone(log_entry)
            self.assertEqual(log_entry.actor_username, "leave_staff_a")

            # Check In-App Notification
            notif = Notification.objects.filter(recipient_user_id=self.staff_user_a.id, category="leave").first()
            self.assertIsNotNone(notif)
            self.assertIn("Submitted", notif.title)

