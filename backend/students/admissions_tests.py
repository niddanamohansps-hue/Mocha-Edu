import io
import uuid as uuid_module
from datetime import date
from unittest.mock import patch, MagicMock
from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection
from django.test import TransactionTestCase, override_settings
from django_tenants.utils import tenant_context
from rest_framework.test import APIClient

from academics.models import AcademicLevel, AcademicYear, Program, Section
from accounts.models import User
from core.models import AuditLog
from families.models import Parent, StudentParentRelation
from organizations.models import Domain, Organization
from profiles.models import Profile
from roles.models import Permission, Role, UserRole
from staff.models import StaffMember

from .models import (
    Student,
    StudentLevel,
    AcademicHistory,
    AdmissionEnquiry,
    AdmissionApplication,
    AdmissionDocument,
    AdmissionInterview,
    AdmissionActivityLog,
)
from .admissions_services import (
    generate_enquiry_number,
    generate_application_number,
    transition_application_status,
    enroll_application_as_student,
    convert_enquiry_to_application,
    get_admissions_dashboard_stats,
)


class AdmissionsFixtureMixin:
    SCHEMA_NAME = "adm_school"
    DOMAIN = "adm-test.localhost"
    TENANT_SCHEMAS = ["adm_school", "adm_school2"]

    def _cleanup(self):
        connection.set_schema_to_public()
        for school in Organization.objects.filter(schema_name__in=self.TENANT_SCHEMAS):
            school.delete(force_drop=True)
        User.objects.filter(username__startswith="adm_").delete()

    def _build_school(self, schema_name, domain):
        connection.set_schema_to_public()
        school = Organization.objects.create(schema_name=schema_name, name=f"School {schema_name}")
        Domain.objects.create(domain=domain, tenant=school, is_primary=True)
        return school

    def _build_user(self, username, codenames=None, owner=False):
        connection.set_schema_to_public()
        user = User.objects.create_user(username=username, email=f"{username}@adm.test", password="Pass1234!")
        with tenant_context(self.school):
            if owner:
                role = Role.objects.get(slug="owner")
            else:
                slug = f"adm-{uuid_module.uuid4().hex[:10]}"
                role = Role.objects.create(name=slug, slug=slug, is_system_role=False)
                role.permissions.set(Permission.objects.filter(codename__in=codenames or []))
            UserRole.objects.create(user=user, role=role)
        return user

    def _client_as(self, user):
        client = APIClient()
        resp = client.post("/api/auth/login/", {"username": user.username, "password": "Pass1234!"}, HTTP_HOST=self.DOMAIN)
        assert resp.status_code == 200, resp.data
        return client

    def setUp(self):
        self.addCleanup(self._cleanup)
        self._cleanup()
        self.school = self._build_school(self.SCHEMA_NAME, self.DOMAIN)

        # 1. Create Users in public schema
        connection.set_schema_to_public()
        self.owner_user = User.objects.create_user(
            username="adm_owner", email="adm_owner@adm.test", password="Pass1234!"
        )
        self.staff_user = User.objects.create_user(
            username="adm_staff", email="adm_staff@adm.test", password="Pass1234!"
        )
        self.viewer_user = User.objects.create_user(
            username="adm_viewer", email="adm_viewer@adm.test", password="Pass1234!"
        )

        # 2. All tenant data in tenant schema
        with tenant_context(self.school):
            from roles.constants import SYSTEM_PERMISSIONS
            for p in SYSTEM_PERMISSIONS:
                Permission.objects.get_or_create(
                    codename=p["codename"],
                    defaults={"name": p["name"], "module": p["module"], "description": p["description"]},
                )

            # Owner
            owner_role = Role.objects.get(slug="owner")
            UserRole.objects.create(user=self.owner_user, role=owner_role)

            # Staff role with admissions permissions
            staff_role, _ = Role.objects.get_or_create(
                slug="staff", defaults={"name": "Staff", "is_system_role": True}
            )
            staff_role.permissions.set(
                Permission.objects.filter(
                    codename__in=[
                        "view_admissions",
                        "manage_admission_enquiries",
                        "manage_admission_applications",
                        "review_admission_documents",
                        "review_admission_applications",
                        "make_admission_decisions",
                        "enroll_admitted_students",
                    ]
                )
            )
            UserRole.objects.create(user=self.staff_user, role=staff_role)

            # Staff profile & member
            staff_profile = Profile.objects.filter(user_id=self.staff_user.id).first()
            if not staff_profile:
                staff_profile = Profile.objects.create(
                    user_id=self.staff_user.id, first_name="Admissions", last_name="Officer"
                )
            self.staff_member, _ = StaffMember.objects.get_or_create(
                profile=staff_profile, defaults={"employee_id": "EMP-ADM-01"}
            )

            # Viewer role
            viewer_role = Role.objects.create(
                name="Admissions Viewer", slug=f"adm-view-{uuid_module.uuid4().hex[:8]}", is_system_role=False
            )
            viewer_role.permissions.set(Permission.objects.filter(codename="view_admissions"))
            UserRole.objects.create(user=self.viewer_user, role=viewer_role)

            # Academics Setup
            self.program = Program.objects.create(name="Primary School", code="PRI")
            self.level_1 = AcademicLevel.objects.create(program=self.program, name="Grade 1", order=1)
            self.level_2 = AcademicLevel.objects.create(program=self.program, name="Grade 2", order=2)
            self.section_a = Section.objects.create(level=self.level_1, name="A")
            self.academic_year = AcademicYear.objects.create(
                name="2026-27",
                start_date=date(2026, 4, 1),
                end_date=date(2027, 3, 31),
                is_current=True,
            )


class AdmissionsApiTests(AdmissionsFixtureMixin, TransactionTestCase):
    def test_enquiry_lifecycle_and_conversion(self):
        client = self._client_as(self.staff_user)

        # 1. Create Enquiry
        payload = {
            "student_name": "Aarav Sharma",
            "date_of_birth": "2019-05-15",
            "gender": "male",
            "guardian_name": "Rajesh Sharma",
            "guardian_relationship": "father",
            "guardian_phone": "+919876543210",
            "guardian_email": "rajesh@example.com",
            "address": "123 MG Road, New Delhi",
            "previous_school": "Little Star Play School",
            "academic_year": "2026-27",
            "academic_year_ref": str(self.academic_year.id),
            "preferred_level": str(self.level_1.id),
            "source": "walk_in",
            "notes": "Interested in morning bus route.",
        }
        res = client.post("/api/admissions/enquiries/", payload, format="json", HTTP_HOST=self.DOMAIN)
        self.assertEqual(res.status_code, 201, res.data)
        enquiry_id = res.data["id"]
        enquiry_num = res.data["enquiry_number"]
        self.assertTrue(enquiry_num.startswith("ENQ-"))

        # 2. List & Search
        res_list = client.get("/api/admissions/enquiries/?search=Aarav", HTTP_HOST=self.DOMAIN)
        self.assertEqual(res_list.status_code, 200)
        self.assertEqual(len(res_list.data["results"]), 1)

        # 3. Patch Enquiry
        res_patch = client.patch(
            f"/api/admissions/enquiries/{enquiry_id}/",
            {"status": "contacted", "notes": "Called guardian. Scheduled visit."},
            format="json",
            HTTP_HOST=self.DOMAIN,
        )
        self.assertEqual(res_patch.status_code, 200)
        self.assertEqual(res_patch.data["status"], "contacted")

        # 4. Convert Enquiry to Application
        res_convert = client.post(
            f"/api/admissions/enquiries/{enquiry_id}/convert/",
            {},
            format="json",
            HTTP_HOST=self.DOMAIN,
        )
        self.assertEqual(res_convert.status_code, 201, res_convert.data)
        app_data = res_convert.data
        self.assertTrue(app_data["application_number"].startswith("APP-"))
        self.assertEqual(app_data["status"], "draft")
        self.assertEqual(app_data["first_name"], "Aarav")
        self.assertEqual(app_data["last_name"], "Sharma")
        self.assertEqual(app_data["guardian_first_name"], "Rajesh")
        self.assertEqual(str(app_data["enquiry"]), str(enquiry_id))

        # Verify enquiry status updated to converted
        with tenant_context(self.school):
            enq = AdmissionEnquiry.objects.get(id=enquiry_id)
            self.assertEqual(enq.status, "converted")

    def test_application_workflow_and_state_machine(self):
        client = self._client_as(self.staff_user)

        # Create Application directly
        app_payload = {
            "first_name": "Diya",
            "last_name": "Patel",
            "date_of_birth": "2018-08-20",
            "gender": "female",
            "phone": "+919811223344",
            "email": "diya.parent@example.com",
            "address": "45 Lakeview, Mumbai",
            "previous_school": "Modern Prep",
            "last_grade_passed": "Kindergarten",
            "guardian_first_name": "Suresh",
            "guardian_last_name": "Patel",
            "guardian_relationship": "father",
            "guardian_phone": "+919811223344",
            "guardian_email": "diya.parent@example.com",
            "academic_year": "2026-27",
            "academic_year_ref": str(self.academic_year.id),
            "level": str(self.level_1.id),
        }
        res = client.post("/api/admissions/applications/", app_payload, format="json", HTTP_HOST=self.DOMAIN)
        self.assertEqual(res.status_code, 201, res.data)
        app_id = res.data["id"]
        self.assertEqual(res.data["status"], "draft")

        # Invalid transition: draft directly to enrolled must fail
        res_invalid = client.post(
            f"/api/admissions/applications/{app_id}/status/",
            {"status": "enrolled"},
            format="json",
            HTTP_HOST=self.DOMAIN,
        )
        self.assertEqual(res_invalid.status_code, 400)

        # Valid transition: draft -> submitted
        res_sub = client.post(
            f"/api/admissions/applications/{app_id}/status/",
            {"status": "submitted", "notes": "Application form received"},
            format="json",
            HTTP_HOST=self.DOMAIN,
        )
        self.assertEqual(res_sub.status_code, 200)
        self.assertEqual(res_sub.data["status"], "submitted")

        # Transition: submitted -> under_review
        res_review = client.post(
            f"/api/admissions/applications/{app_id}/status/",
            {"status": "under_review"},
            format="json",
            HTTP_HOST=self.DOMAIN,
        )
        self.assertEqual(res_review.status_code, 200)
        self.assertEqual(res_review.data["status"], "under_review")

        # Assign Reviewer
        res_assign = client.post(
            f"/api/admissions/applications/{app_id}/assign/",
            {"staff_id": str(self.staff_member.id)},
            format="json",
            HTTP_HOST=self.DOMAIN,
        )
        self.assertEqual(res_assign.status_code, 200)
        self.assertEqual(str(res_assign.data["assigned_reviewer"]), str(self.staff_member.id))

        # Check activity logs populated
        with tenant_context(self.school):
            activities = AdmissionActivityLog.objects.filter(application_id=app_id)
            self.assertGreaterEqual(activities.count(), 3)

    def test_document_upload_verification_and_rejection(self):
        client = self._client_as(self.staff_user)

        with tenant_context(self.school):
            app = AdmissionApplication.objects.create(
                application_number=generate_application_number(),
                first_name="Rohan",
                last_name="Verma",
                date_of_birth="2018-01-01",
                gender="male",
                guardian_first_name="Anil",
                guardian_last_name="Verma",
                guardian_phone="+919999988888",
                academic_year="2026-27",
                level=self.level_1,
                status="documents_pending",
            )
            app_id = str(app.id)

        # 1. Upload Document
        dummy_pdf = io.BytesIO(b"%PDF-1.4 test document content for admissions")
        dummy_file = SimpleUploadedFile("birth_certificate.pdf", dummy_pdf.read(), content_type="application/pdf")
        res_upload = client.post(
            f"/api/admissions/applications/{app_id}/documents/",
            {
                "document_type": "birth_certificate",
                "title": "Birth Certificate - Rohan Verma",
                "file": dummy_file,
            },
            format="multipart",
            HTTP_HOST=self.DOMAIN,
        )
        self.assertEqual(res_upload.status_code, 201, res_upload.data)
        doc_id = res_upload.data["id"]
        self.assertEqual(res_upload.data["verification_status"], "pending")

        # 2. Reject Document with reason
        res_reject = client.post(
            f"/api/admissions/documents/{doc_id}/reject/",
            {"reason": "Image is blurry, please provide a clear scan."},
            format="json",
            HTTP_HOST=self.DOMAIN,
        )
        self.assertEqual(res_reject.status_code, 200)
        self.assertEqual(res_reject.data["verification_status"], "rejected")
        self.assertEqual(res_reject.data["rejection_reason"], "Image is blurry, please provide a clear scan.")

        # 3. Verify Document
        res_verify = client.post(
            f"/api/admissions/documents/{doc_id}/verify/",
            {},
            format="json",
            HTTP_HOST=self.DOMAIN,
        )
        self.assertEqual(res_verify.status_code, 200)
        self.assertEqual(res_verify.data["verification_status"], "verified")
        self.assertEqual(str(res_verify.data["verified_by"]), str(self.staff_member.id))

        # 4. Download Document via authenticated endpoint
        res_dl = client.get(f"/api/admissions/documents/{doc_id}/download/", HTTP_HOST=self.DOMAIN)
        self.assertEqual(res_dl.status_code, 200)
        self.assertIn("inline", res_dl["Content-Disposition"])

    def test_interview_and_assessment_recording(self):
        client = self._client_as(self.staff_user)

        with tenant_context(self.school):
            app = AdmissionApplication.objects.create(
                application_number=generate_application_number(),
                first_name="Kavya",
                last_name="Nair",
                date_of_birth="2017-03-10",
                gender="female",
                guardian_first_name="Ramesh",
                guardian_last_name="Nair",
                guardian_phone="+919777766666",
                academic_year="2026-27",
                level=self.level_1,
                status="assessment_pending",
            )
            app_id = str(app.id)

        # Schedule Interview
        sched_payload = {
            "interview_type": "student_interview",
            "scheduled_at": "2026-04-10T10:00:00Z",
            "interviewer": str(self.staff_member.id),
            "status": "scheduled",
        }
        res_sched = client.post(
            f"/api/admissions/applications/{app_id}/interviews/",
            sched_payload,
            format="json",
            HTTP_HOST=self.DOMAIN,
        )
        self.assertEqual(res_sched.status_code, 201, res_sched.data)
        int_id = res_sched.data["id"]

        # Evaluate Interview
        eval_payload = {
            "status": "completed",
            "score": "92.50",
            "recommendation": "recommended",
            "feedback": "Excellent communication skills and strong basic numeracy.",
        }
        res_eval = client.patch(
            f"/api/admissions/interviews/{int_id}/",
            eval_payload,
            format="json",
            HTTP_HOST=self.DOMAIN,
        )
        self.assertEqual(res_eval.status_code, 200)
        self.assertEqual(res_eval.data["recommendation"], "recommended")
        self.assertEqual(float(res_eval.data["score"]), 92.50)

    def test_decision_and_idempotent_student_enrollment(self):
        client = self._client_as(self.staff_user)

        with tenant_context(self.school):
            app = AdmissionApplication.objects.create(
                application_number=generate_application_number(),
                first_name="Arjun",
                middle_name="K.",
                last_name="Reddy",
                date_of_birth=date(2018, 9, 12),
                gender="male",
                phone="+919876500000",
                email="arjun.reddy@example.com",
                address="78 Banjara Hills, Hyderabad",
                previous_school="Early Steps Academy",
                last_grade_passed="UKG",
                guardian_first_name="Vijay",
                guardian_last_name="Reddy",
                guardian_relationship="father",
                guardian_phone="+919876500000",
                guardian_email="vijay.reddy@example.com",
                guardian_occupation="Doctor",
                academic_year="2026-27",
                academic_year_ref=self.academic_year,
                level=self.level_1,
                status="under_review",
            )
            app_id = str(app.id)

        # 1. Decision: Reject without reason should fail
        res_rej_fail = client.post(
            f"/api/admissions/applications/{app_id}/decide/",
            {"decision": "rejected", "reason": ""},
            format="json",
            HTTP_HOST=self.DOMAIN,
        )
        self.assertEqual(res_rej_fail.status_code, 400)

        # 2. Decision: Approve
        res_app = client.post(
            f"/api/admissions/applications/{app_id}/decide/",
            {"decision": "approved", "notes": "Approved based on interview score"},
            format="json",
            HTTP_HOST=self.DOMAIN,
        )
        self.assertEqual(res_app.status_code, 200)
        self.assertEqual(res_app.data["status"], "approved")

        # 3. Enroll: Convert into active Student record
        res_enroll = client.post(
            f"/api/admissions/applications/{app_id}/enroll/",
            {"section_id": str(self.section_a.id)},
            format="json",
            HTTP_HOST=self.DOMAIN,
        )
        self.assertEqual(res_enroll.status_code, 201, res_enroll.data)
        enrollment_id = res_enroll.data["enrollment_id"]
        student_id = res_enroll.data["student_id"]
        self.assertTrue(enrollment_id.startswith("STD-"))

        # 4. Verify Database Records Created Transactionally
        with tenant_context(self.school):
            student = Student.objects.get(id=student_id)
            self.assertEqual(student.enrollment_id, enrollment_id)
            self.assertEqual(student.status, "active")
            self.assertEqual(student.profile.first_name, "Arjun")
            self.assertEqual(student.profile.last_name, "Reddy")

            # Academic placement
            sl = StudentLevel.objects.get(student=student, is_current=True)
            self.assertEqual(sl.level, self.level_1)
            self.assertEqual(sl.section, self.section_a)
            self.assertEqual(sl.academic_year, "2026-27")

            # Academic History
            hist = AcademicHistory.objects.filter(student=student).first()
            self.assertIsNotNone(hist)
            self.assertEqual(hist.previous_school, "Early Steps Academy")

            # Guardian relation
            rel = StudentParentRelation.objects.filter(student=student).first()
            self.assertIsNotNone(rel)
            self.assertEqual(rel.parent.profile.first_name, "Vijay")
            self.assertTrue(rel.is_primary_contact)

            # Application is marked ENROLLED
            app.refresh_from_db()
            self.assertEqual(app.status, "enrolled")
            self.assertEqual(app.student, student)

            # AuditLog was recorded
            audit_entry = AuditLog.objects.filter(model_name="Student", object_id=str(student.id)).first()
            self.assertIsNotNone(audit_entry)

        # 5. Idempotent Guard: Repeating enrollment must fail cleanly
        res_repeat = client.post(
            f"/api/admissions/applications/{app_id}/enroll/",
            {"section_id": str(self.section_a.id)},
            format="json",
            HTTP_HOST=self.DOMAIN,
        )
        self.assertEqual(res_repeat.status_code, 400)
        self.assertIn("already enrolled", str(res_repeat.data))

    def test_dashboard_stats_and_rbac(self):
        client = self._client_as(self.staff_user)

        res_stats = client.get("/api/admissions/dashboard/", HTTP_HOST=self.DOMAIN)
        self.assertEqual(res_stats.status_code, 200)
        self.assertIn("total_enquiries", res_stats.data)
        self.assertIn("total_applications", res_stats.data)
        self.assertIn("conversion_rate", res_stats.data)

        # Viewer without manage permissions cannot create enquiry
        viewer_client = self._client_as(self.viewer_user)
        res_unauth = viewer_client.post(
            "/api/admissions/enquiries/",
            {"student_name": "Test", "guardian_phone": "123", "academic_year": "2026-27"},
            format="json",
            HTTP_HOST=self.DOMAIN,
        )
        self.assertEqual(res_unauth.status_code, 403)

    def test_public_admissions_info(self):
        client = APIClient()
        res = client.get("/api/admissions/public/info/", HTTP_HOST=self.DOMAIN)
        self.assertEqual(res.status_code, 200)
        self.assertIn("institution", res.data)
        self.assertEqual(res.data["institution"]["name"], "School adm_school")
        self.assertIn("academic_years", res.data)
        self.assertTrue(len(res.data["academic_years"]) >= 1)
        self.assertIn("levels", res.data)
        self.assertTrue(len(res.data["levels"]) >= 1)
        self.assertIn("upload_policy", res.data)
        self.assertEqual(res.data["upload_policy"]["max_file_size_mb"], 10)
        self.assertIn(".pdf", res.data["upload_policy"]["allowed_extensions"])

    def test_public_enquiry_submission(self):
        client = APIClient()

        # 1. Missing consent must fail
        payload_no_consent = {
            "student_name": "Rohan Das",
            "guardian_name": "Sanjay Das",
            "guardian_relationship": "father",
            "guardian_phone": "9876543210",
            "preferred_level": str(self.level_1.id),
            "academic_year_ref": str(self.academic_year.id),
            "consent": False,
        }
        res_fail = client.post(
            "/api/admissions/public/enquiries/",
            payload_no_consent,
            format="json",
            HTTP_HOST=self.DOMAIN,
        )
        self.assertEqual(res_fail.status_code, 400)
        self.assertIn("consent", str(res_fail.data).lower())

        # 2. Valid submission succeeds
        payload_valid = dict(payload_no_consent)
        payload_valid["consent"] = True
        payload_valid["guardian_email"] = "sanjay.das@example.com"
        res_ok = client.post(
            "/api/admissions/public/enquiries/",
            payload_valid,
            format="json",
            HTTP_HOST=self.DOMAIN,
        )
        self.assertEqual(res_ok.status_code, 201)
        self.assertTrue(res_ok.data["success"])
        enq_num = res_ok.data["enquiry_number"]
        self.assertTrue(enq_num.startswith("ENQ-2026-"))

        with tenant_context(self.school):
            enq = AdmissionEnquiry.objects.filter(enquiry_number=enq_num).first()
            self.assertIsNotNone(enq)
            self.assertEqual(enq.source, "website")
            self.assertEqual(enq.status, "new")
            self.assertEqual(enq.student_name, "Rohan Das")

    def test_public_application_submission_and_capability_token(self):
        client = APIClient()

        # Submit valid application
        payload = {
            "first_name": "Priya",
            "last_name": "Nair",
            "date_of_birth": "2015-05-10",
            "gender": "female",
            "guardian_first_name": "Ramesh",
            "guardian_last_name": "Nair",
            "guardian_relationship": "father",
            "guardian_phone": "9988776655",
            "guardian_email": "ramesh.nair@example.com",
            "academic_year_ref": str(self.academic_year.id),
            "level": str(self.level_1.id),
            "consent": True,
            # Attempt to sneak in privileged fields - must be ignored!
            "status": "approved",
            "assigned_reviewer": str(self.staff_member.id),
        }

        res = client.post(
            "/api/admissions/public/applications/",
            payload,
            format="json",
            HTTP_HOST=self.DOMAIN,
        )
        self.assertEqual(res.status_code, 201)
        self.assertTrue(res.data["success"])
        app_num = res.data["application_number"]
        raw_token = res.data["access_token"]
        self.assertTrue(len(raw_token) > 20)
        self.assertEqual(res.data["status"], "submitted")

        with tenant_context(self.school):
            app = AdmissionApplication.objects.filter(application_number=app_num).first()
            self.assertIsNotNone(app)
            self.assertEqual(app.status, "submitted")  # Privileged status was blocked!
            self.assertIsNone(app.assigned_reviewer)  # Reviewer injection was blocked!
            # DB stores SHA-256 hash, NOT raw token
            import hashlib
            expected_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
            self.assertEqual(app.access_token_hash, expected_hash)

            # Activity log was created
            log = AdmissionActivityLog.objects.filter(application=app, action="submitted").first()
            self.assertIsNotNone(log)

    def test_public_application_status_lookup_security(self):
        client = APIClient()

        # 1. Create test application with known token
        import secrets, hashlib
        raw_token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()

        with tenant_context(self.school):
            app = AdmissionApplication.objects.create(
                application_number="APP-2026-9999",
                first_name="Aarav",
                last_name="Sharma",
                date_of_birth=date(2014, 8, 12),
                gender="male",
                guardian_first_name="Rajesh",
                guardian_last_name="Sharma",
                guardian_relationship="father",
                guardian_phone="9876543210",
                academic_year=self.academic_year.name,
                academic_year_ref=self.academic_year,
                level=self.level_1,
                status="documents_pending",
                notes="Internal note: applicant interview required.",
                access_token_hash=token_hash,
                access_token_expires_at=date(2027, 1, 1),
            )

        app_num = "APP-2026-9999"

        # 2. Missing token -> 401
        res_no_token = client.get(
            f"/api/admissions/public/applications/{app_num}/status/",
            HTTP_HOST=self.DOMAIN,
        )
        self.assertEqual(res_no_token.status_code, 401)

        # 3. Invalid token -> 404 (Uniform constant-time 404 eliminates enumeration oracle)
        res_wrong_token = client.get(
            f"/api/admissions/public/applications/{app_num}/status/",
            HTTP_HOST=self.DOMAIN,
            HTTP_X_APPLICATION_TOKEN="wrong_token_value_12345",
        )
        self.assertEqual(res_wrong_token.status_code, 404)
        self.assertIn("Application not found or access credentials invalid", res_wrong_token.data.get("error", ""))

        # 4. Unknown application -> 404
        res_unknown = client.get(
            "/api/admissions/public/applications/APP-9999-0000/status/",
            HTTP_HOST=self.DOMAIN,
            HTTP_X_APPLICATION_TOKEN=raw_token,
        )
        self.assertEqual(res_unknown.status_code, 404)
        self.assertIn("Application not found or access credentials invalid", res_unknown.data.get("error", ""))

        # 5. Valid token -> 200 OK with sanitized public data
        res_ok = client.get(
            f"/api/admissions/public/applications/{app_num}/status/",
            HTTP_HOST=self.DOMAIN,
            HTTP_X_APPLICATION_TOKEN=raw_token,
        )
        self.assertEqual(res_ok.status_code, 200)
        self.assertEqual(res_ok.data["application_number"], app_num)
        self.assertEqual(res_ok.data["student_masked_name"], "Aarav S****a")
        self.assertEqual(res_ok.data["status"], "documents_pending")
        self.assertEqual(res_ok.data["status_display"], "Documents Required")
        self.assertTrue(res_ok.data["can_upload_documents"])
        # Ensure internal notes and reviewer are NOT exposed in public response
        self.assertNotIn("notes", res_ok.data)
        self.assertNotIn("assigned_reviewer", res_ok.data)
        self.assertNotIn("interview required", str(res_ok.data))

    def test_public_document_upload_and_verification(self):
        client = APIClient()

        import secrets, hashlib
        raw_token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()

        with tenant_context(self.school):
            app = AdmissionApplication.objects.create(
                application_number="APP-2026-8888",
                first_name="Maya",
                last_name="Verma",
                date_of_birth=date(2015, 3, 20),
                gender="female",
                guardian_first_name="Sunil",
                guardian_last_name="Verma",
                guardian_relationship="father",
                guardian_phone="9876543211",
                academic_year=self.academic_year.name,
                academic_year_ref=self.academic_year,
                level=self.level_1,
                status="documents_pending",
                access_token_hash=token_hash,
                access_token_expires_at=date(2027, 1, 1),
            )

        app_num = "APP-2026-8888"

        # 1. Upload without token -> 401
        dummy_pdf = SimpleUploadedFile("birth.pdf", b"%PDF-1.4 dummy", content_type="application/pdf")
        res_no_tok = client.post(
            f"/api/admissions/public/applications/{app_num}/documents/",
            {"document_type": "birth_certificate", "file": dummy_pdf},
            format="multipart",
            HTTP_HOST=self.DOMAIN,
        )
        self.assertEqual(res_no_tok.status_code, 401)

        # 2. Upload with invalid extension -> 400
        bad_file = SimpleUploadedFile("script.sh", b"echo evil", content_type="application/x-sh")
        res_bad_ext = client.post(
            f"/api/admissions/public/applications/{app_num}/documents/",
            {"document_type": "birth_certificate", "file": bad_file},
            format="multipart",
            HTTP_HOST=self.DOMAIN,
            HTTP_X_APPLICATION_TOKEN=raw_token,
        )
        self.assertEqual(res_bad_ext.status_code, 400)
        self.assertIn("Unsupported file format", str(res_bad_ext.data))

        # 3. Valid document upload -> 201 Created
        good_pdf = SimpleUploadedFile("birth_certificate.pdf", b"%PDF-1.4 valid content", content_type="application/pdf")
        res_upload = client.post(
            f"/api/admissions/public/applications/{app_num}/documents/",
            {"document_type": "birth_certificate", "title": "Birth Certificate", "file": good_pdf},
            format="multipart",
            HTTP_HOST=self.DOMAIN,
            HTTP_X_APPLICATION_TOKEN=raw_token,
        )
        self.assertEqual(res_upload.status_code, 201)
        self.assertTrue(res_upload.data["success"])
        doc_id = res_upload.data["document_id"]

        # 4. Document is in status response as pending
        res_status = client.get(
            f"/api/admissions/public/applications/{app_num}/status/",
            HTTP_HOST=self.DOMAIN,
            HTTP_X_APPLICATION_TOKEN=raw_token,
        )
        self.assertEqual(res_status.status_code, 200)
        self.assertEqual(len(res_status.data["documents"]), 1)
        self.assertEqual(res_status.data["documents"][0]["verification_status"], "pending")

        # 5. Staff verifies document
        staff_client = self._client_as(self.staff_user)
        res_verify = staff_client.post(
            f"/api/admissions/documents/{doc_id}/verify/",
            HTTP_HOST=self.DOMAIN,
        )
        self.assertEqual(res_verify.status_code, 200)

        # 6. Status response now shows verified
        res_status2 = client.get(
            f"/api/admissions/public/applications/{app_num}/status/",
            HTTP_HOST=self.DOMAIN,
            HTTP_X_APPLICATION_TOKEN=raw_token,
        )
        self.assertEqual(res_status2.data["documents"][0]["verification_status"], "verified")

    def test_public_admissions_tenant_isolation(self):
        client = APIClient()

        import secrets, hashlib
        raw_token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()

        # Build school 2
        school2 = self._build_school("adm_school2", "adm-school2.localhost")

        # Create application in school 1
        with tenant_context(self.school):
            AdmissionApplication.objects.create(
                application_number="APP-2026-7777",
                first_name="Kiran",
                last_name="Rao",
                date_of_birth=date(2015, 6, 1),
                gender="female",
                guardian_first_name="Anand",
                guardian_last_name="Rao",
                guardian_relationship="father",
                guardian_phone="9876543212",
                academic_year=self.academic_year.name,
                academic_year_ref=self.academic_year,
                level=self.level_1,
                status="submitted",
                access_token_hash=token_hash,
                access_token_expires_at=date(2027, 1, 1),
            )

        # Querying school 1 domain with correct token works
        res_school1 = client.get(
            "/api/admissions/public/applications/APP-2026-7777/status/",
            HTTP_HOST=self.DOMAIN,
            HTTP_X_APPLICATION_TOKEN=raw_token,
        )
        self.assertEqual(res_school1.status_code, 200)

        # Multi-Tenant Isolation Checks on School 2 Host for School 1 Data:
        # 1. Querying school 2 domain with school 1 application number must return 404 (isolated schema)
        res_school2 = client.get(
            "/api/admissions/public/applications/APP-2026-7777/status/",
            HTTP_HOST="adm-school2.localhost",
            HTTP_X_APPLICATION_TOKEN=raw_token,
        )
        self.assertEqual(res_school2.status_code, 404)

        # 2. Token rotation on school 2 domain must return 404
        res_rot_school2 = client.post(
            "/api/admissions/public/applications/APP-2026-7777/rotate-token/",
            HTTP_HOST="adm-school2.localhost",
            HTTP_X_APPLICATION_TOKEN=raw_token,
        )
        self.assertEqual(res_rot_school2.status_code, 404)

        # 3. Document upload on school 2 domain must return 404
        dummy_pdf = SimpleUploadedFile("doc.pdf", b"%PDF-1.4 sample content", content_type="application/pdf")
        res_up_school2 = client.post(
            "/api/admissions/public/applications/APP-2026-7777/documents/",
            {"document_type": "birth_certificate", "title": "Birth Certificate", "file": dummy_pdf},
            format="multipart",
            HTTP_HOST="adm-school2.localhost",
            HTTP_X_APPLICATION_TOKEN=raw_token,
        )
        self.assertEqual(res_up_school2.status_code, 404)

    def test_public_token_rotation(self):
        client = APIClient()
        import secrets, hashlib
        raw_token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()

        with tenant_context(self.school):
            app = AdmissionApplication.objects.create(
                application_number="APP-2026-6666",
                first_name="Ravi",
                last_name="Teja",
                date_of_birth=date(2015, 7, 10),
                gender="male",
                guardian_first_name="Suresh",
                guardian_last_name="Teja",
                guardian_relationship="father",
                guardian_phone="9876543219",
                academic_year=self.academic_year.name,
                academic_year_ref=self.academic_year,
                level=self.level_1,
                status="submitted",
                access_token_hash=token_hash,
                access_token_expires_at=date(2027, 1, 1),
            )

        app_num = "APP-2026-6666"

        # Missing token -> 401
        res_no_tok = client.post(
            f"/api/admissions/public/applications/{app_num}/rotate-token/",
            HTTP_HOST=self.DOMAIN,
        )
        self.assertEqual(res_no_tok.status_code, 401)

        # Invalid token -> 404 (Oracle elimination)
        res_bad_tok = client.post(
            f"/api/admissions/public/applications/{app_num}/rotate-token/",
            HTTP_HOST=self.DOMAIN,
            HTTP_X_APPLICATION_TOKEN="invalid_secret_token",
        )
        self.assertEqual(res_bad_tok.status_code, 404)

        # Valid rotation -> 200 with new token
        res_rotate = client.post(
            f"/api/admissions/public/applications/{app_num}/rotate-token/",
            HTTP_HOST=self.DOMAIN,
            HTTP_X_APPLICATION_TOKEN=raw_token,
        )
        self.assertEqual(res_rotate.status_code, 200)
        self.assertTrue(res_rotate.data["success"])
        new_token = res_rotate.data["access_token"]
        self.assertNotEqual(new_token, raw_token)
        self.assertEqual(res_rotate.headers.get("Cache-Control"), "no-store, no-cache, must-revalidate, private")

        # Old token is now invalid (returns 404)
        res_old_check = client.get(
            f"/api/admissions/public/applications/{app_num}/status/",
            HTTP_HOST=self.DOMAIN,
            HTTP_X_APPLICATION_TOKEN=raw_token,
        )
        self.assertEqual(res_old_check.status_code, 404)

        # New token succeeds (returns 200)
        res_new_check = client.get(
            f"/api/admissions/public/applications/{app_num}/status/",
            HTTP_HOST=self.DOMAIN,
            HTTP_X_APPLICATION_TOKEN=new_token,
        )
        self.assertEqual(res_new_check.status_code, 200)

        # Activity log records rotation
        with tenant_context(self.school):
            log = AdmissionActivityLog.objects.filter(application=app, action="token_rotated").first()
            self.assertIsNotNone(log)

    def test_staff_token_management(self):
        import secrets, hashlib
        raw_token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()

        with tenant_context(self.school):
            app = AdmissionApplication.objects.create(
                application_number="APP-2026-5555",
                first_name="Anita",
                last_name="Roy",
                date_of_birth=date(2015, 9, 15),
                gender="female",
                guardian_first_name="Sunil",
                guardian_last_name="Roy",
                guardian_relationship="father",
                guardian_phone="9876543299",
                academic_year=self.academic_year.name,
                academic_year_ref=self.academic_year,
                level=self.level_1,
                status="submitted",
                access_token_hash=token_hash,
                access_token_expires_at=date(2027, 1, 1),
            )

        app_id = str(app.id)
        staff_client = self._client_as(self.staff_user)
        viewer_client = self._client_as(self.viewer_user)
        public_client = APIClient()

        # Viewer without manage permissions is rejected (403)
        res_view_rotate = viewer_client.post(
            f"/api/admissions/applications/{app_id}/rotate-token/",
            HTTP_HOST=self.DOMAIN,
        )
        self.assertEqual(res_view_rotate.status_code, 403)

        res_view_revoke = viewer_client.post(
            f"/api/admissions/applications/{app_id}/revoke-token/",
            HTTP_HOST=self.DOMAIN,
        )
        self.assertEqual(res_view_revoke.status_code, 403)

        # Staff revokes token
        res_staff_revoke = staff_client.post(
            f"/api/admissions/applications/{app_id}/revoke-token/",
            {"reason": "Security compromise reported by parent"},
            format="json",
            HTTP_HOST=self.DOMAIN,
        )
        self.assertEqual(res_staff_revoke.status_code, 200)

        # Public access with original token is now denied (404)
        res_pub_check = public_client.get(
            "/api/admissions/public/applications/APP-2026-5555/status/",
            HTTP_HOST=self.DOMAIN,
            HTTP_X_APPLICATION_TOKEN=raw_token,
        )
        self.assertEqual(res_pub_check.status_code, 404)

        # Document upload with revoked token is also denied (404)
        dummy_pdf = SimpleUploadedFile("birth.pdf", b"%PDF-1.4 sample", content_type="application/pdf")
        res_revoked_upload = public_client.post(
            "/api/admissions/public/applications/APP-2026-5555/documents/",
            {"document_type": "birth_certificate", "title": "Birth Certificate", "file": dummy_pdf},
            format="multipart",
            HTTP_HOST=self.DOMAIN,
            HTTP_X_APPLICATION_TOKEN=raw_token,
        )
        self.assertEqual(res_revoked_upload.status_code, 404)

        # Staff rotates token to generate a new capability token
        res_staff_rotate = staff_client.post(
            f"/api/admissions/applications/{app_id}/rotate-token/",
            {"reason": "Issued new token to parent via verified in-person verification"},
            format="json",
            HTTP_HOST=self.DOMAIN,
        )
        self.assertEqual(res_staff_rotate.status_code, 200)
        new_token = res_staff_rotate.data["access_token"]
        self.assertNotEqual(new_token, raw_token)

        # Public access with new token works
        res_pub_new = public_client.get(
            "/api/admissions/public/applications/APP-2026-5555/status/",
            HTTP_HOST=self.DOMAIN,
            HTTP_X_APPLICATION_TOKEN=new_token,
        )
        self.assertEqual(res_pub_new.status_code, 200)

        # Expired token cannot access status or upload documents
        with tenant_context(self.school):
            from datetime import timedelta
            from django.utils import timezone
            app.access_token_expires_at = timezone.now() - timedelta(days=1)
            app.save(update_fields=["access_token_expires_at"])

        res_expired_status = public_client.get(
            "/api/admissions/public/applications/APP-2026-5555/status/",
            HTTP_HOST=self.DOMAIN,
            HTTP_X_APPLICATION_TOKEN=new_token,
        )
        self.assertEqual(res_expired_status.status_code, 404)

        res_expired_upload = public_client.post(
            "/api/admissions/public/applications/APP-2026-5555/documents/",
            {"document_type": "birth_certificate", "title": "Birth Certificate", "file": dummy_pdf},
            format="multipart",
            HTTP_HOST=self.DOMAIN,
            HTTP_X_APPLICATION_TOKEN=new_token,
        )
        self.assertEqual(res_expired_upload.status_code, 404)

    def test_document_upload_magic_byte_validation(self):
        client = APIClient()
        import secrets, hashlib
        raw_token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()

        with tenant_context(self.school):
            app = AdmissionApplication.objects.create(
                application_number="APP-2026-4444",
                first_name="Deepak",
                last_name="Chopra",
                date_of_birth=date(2015, 1, 1),
                gender="male",
                guardian_first_name="Anil",
                guardian_last_name="Chopra",
                guardian_relationship="father",
                guardian_phone="9876543288",
                academic_year=self.academic_year.name,
                academic_year_ref=self.academic_year,
                level=self.level_1,
                status="documents_pending",
                access_token_hash=token_hash,
                access_token_expires_at=date(2027, 1, 1),
            )

        app_num = "APP-2026-4444"

        # 1. Empty file (0 bytes) -> 400
        empty_file = SimpleUploadedFile("empty.pdf", b"", content_type="application/pdf")
        res_empty = client.post(
            f"/api/admissions/public/applications/{app_num}/documents/",
            {"document_type": "birth_certificate", "title": "Birth Certificate", "file": empty_file},
            format="multipart",
            HTTP_HOST=self.DOMAIN,
            HTTP_X_APPLICATION_TOKEN=raw_token,
        )
        self.assertEqual(res_empty.status_code, 400)
        self.assertTrue("Empty files are not allowed" in str(res_empty.data) or "empty" in str(res_empty.data).lower())

        # 2. Dangerous double extension -> 400
        evil_double = SimpleUploadedFile("exploit.php.pdf", b"%PDF-1.4 malicious script payload", content_type="application/pdf")
        res_double = client.post(
            f"/api/admissions/public/applications/{app_num}/documents/",
            {"document_type": "birth_certificate", "title": "Double Ext Doc", "file": evil_double},
            format="multipart",
            HTTP_HOST=self.DOMAIN,
            HTTP_X_APPLICATION_TOKEN=raw_token,
        )
        self.assertEqual(res_double.status_code, 400)
        self.assertIn("dangerous", str(res_double.data).lower())

        # 3. Extension spoofing (fake PDF containing plain text) -> 400
        fake_pdf = SimpleUploadedFile("fake.pdf", b"PLAIN TEXT THIS IS NOT A PDF", content_type="application/pdf")
        res_fake = client.post(
            f"/api/admissions/public/applications/{app_num}/documents/",
            {"document_type": "birth_certificate", "title": "Fake PDF Doc", "file": fake_pdf},
            format="multipart",
            HTTP_HOST=self.DOMAIN,
            HTTP_X_APPLICATION_TOKEN=raw_token,
        )
        self.assertEqual(res_fake.status_code, 400)
        self.assertTrue("not a valid pdf" in str(res_fake.data).lower() or "invalid" in str(res_fake.data).lower())

        # 4. Valid JPEG magic bytes -> 201
        valid_jpeg_bytes = b"\xff\xd8\xff\xe0" + b"\x00" * 32
        valid_jpeg = SimpleUploadedFile("photo.jpg", valid_jpeg_bytes, content_type="image/jpeg")
        res_jpeg = client.post(
            f"/api/admissions/public/applications/{app_num}/documents/",
            {"document_type": "photo", "title": "Passport Photo", "file": valid_jpeg},
            format="multipart",
            HTTP_HOST=self.DOMAIN,
            HTTP_X_APPLICATION_TOKEN=raw_token,
        )
        self.assertEqual(res_jpeg.status_code, 201)

        # 5. Valid PNG magic bytes -> 201
        valid_png_bytes = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
        valid_png = SimpleUploadedFile("avatar.png", valid_png_bytes, content_type="image/png")
        res_png = client.post(
            f"/api/admissions/public/applications/{app_num}/documents/",
            {"document_type": "photo", "title": "Applicant Avatar", "file": valid_png},
            format="multipart",
            HTTP_HOST=self.DOMAIN,
            HTTP_X_APPLICATION_TOKEN=raw_token,
        )
        self.assertEqual(res_png.status_code, 201)

    def test_public_schema_admissions_endpoints_blocked(self):
        client = APIClient()

        # Connect with public schema domain (e.g. localhost)
        for endpoint in [
            "/api/admissions/public/info/",
            "/api/admissions/public/enquiries/",
            "/api/admissions/public/applications/",
            "/api/admissions/public/applications/APP-TEST/status/",
            "/api/admissions/public/applications/APP-TEST/documents/",
            "/api/admissions/public/applications/APP-TEST/rotate-token/",
        ]:
            if "status" in endpoint or "info" in endpoint:
                res = client.get(endpoint, HTTP_HOST="localhost")
            else:
                res = client.post(endpoint, HTTP_HOST="localhost")
            self.assertEqual(res.status_code, 404, f"Endpoint {endpoint} failed to block public schema access")

    def test_private_media_endpoint_blocked(self):
        client = APIClient()
        res_admission_doc = client.get("/media/admission_documents/sample.pdf", HTTP_HOST=self.DOMAIN)
        self.assertEqual(res_admission_doc.status_code, 403)

        res_submission = client.get("/media/submissions/homework.pdf", HTTP_HOST=self.DOMAIN)
        self.assertEqual(res_submission.status_code, 403)

    def test_duplicate_submission_protection(self):
        client = APIClient()
        payload = {
            "first_name": "Siddharth",
            "last_name": "Mukherjee",
            "date_of_birth": "2015-11-20",
            "gender": "male",
            "guardian_first_name": "Subhash",
            "guardian_last_name": "Mukherjee",
            "guardian_relationship": "father",
            "guardian_phone": "9812345678",
            "academic_year_ref": str(self.academic_year.id),
            "level": str(self.level_1.id),
            "consent": True,
        }

        # 1. First legitimate submission
        res1 = client.post("/api/admissions/public/applications/", payload, format="json", HTTP_HOST=self.DOMAIN)
        self.assertEqual(res1.status_code, 201)
        app_num1 = res1.data["application_number"]
        parent_token = res1.data["access_token"]
        self.assertTrue(len(parent_token) > 20)

        # Store original hash in DB
        with tenant_context(self.school):
            app1 = AdmissionApplication.objects.get(application_number=app_num1)
            original_hash = app1.access_token_hash

        # 2. Unauthorized duplicate submission (attacker or unauthenticated duplicate)
        attacker_client = APIClient()
        res2 = attacker_client.post("/api/admissions/public/applications/", payload, format="json", HTTP_HOST=self.DOMAIN)
        # Duplicate submission is rejected (400 Bad Request)
        self.assertEqual(res2.status_code, 400)
        # Attacker receives NO capability token or application number
        self.assertNotIn("access_token", res2.data)
        self.assertNotIn("application_number", res2.data)
        self.assertIn("already been submitted", str(res2.data))

        # 3. Database record count is 1 and original parent's hash was NOT modified/reset
        with tenant_context(self.school):
            app1.refresh_from_db()
            self.assertEqual(app1.access_token_hash, original_hash)
            count = AdmissionApplication.objects.filter(
                first_name="Siddharth", last_name="Mukherjee", guardian_phone="9812345678"
            ).count()
            self.assertEqual(count, 1)

        # 4. Legitimate parent's capability token STILL WORKS
        res_status = client.get(
            f"/api/admissions/public/applications/{app_num1}/status/",
            HTTP_HOST=self.DOMAIN,
            HTTP_X_APPLICATION_TOKEN=parent_token,
        )
        self.assertEqual(res_status.status_code, 200)
        self.assertEqual(res_status.data["application_number"], app_num1)

    def test_rejection_reason_masked_for_non_rejected_documents(self):
        client = APIClient()
        import secrets, hashlib
        raw_token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()

        with tenant_context(self.school):
            app = AdmissionApplication.objects.create(
                application_number="APP-2026-3333",
                first_name="Nandini",
                last_name="Sen",
                date_of_birth=date(2015, 4, 15),
                gender="female",
                guardian_first_name="Amit",
                guardian_last_name="Sen",
                guardian_relationship="father",
                guardian_phone="9876543277",
                academic_year=self.academic_year.name,
                academic_year_ref=self.academic_year,
                level=self.level_1,
                status="documents_pending",
                access_token_hash=token_hash,
                access_token_expires_at=date(2027, 1, 1),
            )
            doc_pending = AdmissionDocument.objects.create(
                application=app,
                document_type="birth_certificate",
                title="Birth Cert",
                file="admission_documents/test_birth.pdf",
                verification_status="pending",
                rejection_reason="Internal staff review note not yet released",
            )

        app_num = "APP-2026-3333"

        res = client.get(
            f"/api/admissions/public/applications/{app_num}/status/",
            HTTP_HOST=self.DOMAIN,
            HTTP_X_APPLICATION_TOKEN=raw_token,
        )
        self.assertEqual(res.status_code, 200)
        docs = res.data["documents"]
        self.assertEqual(len(docs), 1)
        self.assertIsNone(docs[0].get("rejection_reason"))

        # Now mark as rejected
        with tenant_context(self.school):
            doc_pending.verification_status = "rejected"
            doc_pending.rejection_reason = "Document is blurred and unreadable. Please upload a clear scan."
            doc_pending.save()

        res2 = client.get(
            f"/api/admissions/public/applications/{app_num}/status/",
            HTTP_HOST=self.DOMAIN,
            HTTP_X_APPLICATION_TOKEN=raw_token,
        )
        self.assertEqual(res2.status_code, 200)
        docs2 = res2.data["documents"]
        self.assertEqual(docs2[0].get("rejection_reason"), "Document is blurred and unreadable. Please upload a clear scan.")

    def test_private_media_delivery_and_quarantine_controls(self):
        """
        BLK-01 & BLK-04: Verifies private media protection, static URL rejection,
        path traversal defense, and antivirus quarantine download blocking.
        """
        client = APIClient()

        # 1. Direct unauthenticated request to /media/admission_documents/ must be denied (403 Forbidden)
        res_direct = client.get("/media/admission_documents/2026/10/secret.pdf", HTTP_HOST=self.DOMAIN)
        self.assertEqual(res_direct.status_code, 403)
        self.assertIn("Direct access to private files is forbidden", res_direct.content.decode())

        # 2. Directory traversal attempt through /media/ must also be denied (403 Forbidden)
        res_traversal = client.get("/media/public/../admission_documents/secret.pdf", HTTP_HOST=self.DOMAIN)
        self.assertEqual(res_traversal.status_code, 403)

        # Create an application and test documents with different scan statuses
        with tenant_context(self.school):
            app = AdmissionApplication.objects.create(
                application_number="APP-2026-MEDIA-TEST",
                first_name="Priya",
                last_name="Sen",
                date_of_birth="2018-05-15",
                gender="female",
                guardian_first_name="Alok",
                guardian_last_name="Sen",
                guardian_phone="+919876543210",
                academic_year="2026-27",
                academic_year_ref=self.academic_year,
                level=self.level_1,
                status="documents_pending",
            )

            # File 1: Quarantined - scan_status = "pending"
            doc_pending = AdmissionDocument.objects.create(
                application=app,
                document_type="birth_certificate",
                title="Birth Certificate - Pending Scan",
                file=SimpleUploadedFile("birth_pending.pdf", b"%PDF-1.4 sample content", content_type="application/pdf"),
                verification_status="pending",
                scan_status="pending",
            )
            doc_pending_id = str(doc_pending.id)

            # File 2: Quarantined - scan_status = "infected"
            doc_infected = AdmissionDocument.objects.create(
                application=app,
                document_type="previous_marksheet",
                title="Marksheet - Infected",
                file=SimpleUploadedFile("marksheet_bad.pdf", b"%PDF-1.4 infected content", content_type="application/pdf"),
                verification_status="rejected",
                scan_status="infected",
                scan_details="Malware signature detected: Eicar-Test-Signature",
            )
            doc_infected_id = str(doc_infected.id)

            # File 3: Quarantined - scan_status = "error"
            doc_error = AdmissionDocument.objects.create(
                application=app,
                document_type="photo",
                title="Photo - Error Scan",
                file=SimpleUploadedFile("photo_err.jpg", b"\xff\xd8\xff\xe0\x00\x10JFIF", content_type="image/jpeg"),
                verification_status="pending",
                scan_status="error",
                scan_details="Antivirus scanner timeout",
            )
            doc_error_id = str(doc_error.id)

            # File 4: Clean - scan_status = "clean"
            doc_clean = AdmissionDocument.objects.create(
                application=app,
                document_type="address_proof",
                title="Address Proof - Clean",
                file=SimpleUploadedFile("address_clean.pdf", b"%PDF-1.4 clean content", content_type="application/pdf"),
                verification_status="pending",
                scan_status="clean",
                scan_details="Passed ClamAV antivirus inspection.",
            )
            doc_clean_id = str(doc_clean.id)

        # 3. Unauthenticated access to staff download endpoint must fail (401 Unauthorized)
        res_unauth = client.get(f"/api/admissions/documents/{doc_clean_id}/download/", HTTP_HOST=self.DOMAIN)
        self.assertEqual(res_unauth.status_code, 401)

        # 4. Authenticated staff without permissions must fail (403 Forbidden)
        no_perm_user = self._build_user("adm_noperm_user", codenames=[])
        client_no_perm = self._client_as(no_perm_user)
        res_noperm = client_no_perm.get(f"/api/admissions/documents/{doc_clean_id}/download/", HTTP_HOST=self.DOMAIN)
        self.assertEqual(res_noperm.status_code, 403)

        staff_client = self._client_as(self.staff_user)

        # 5. Staff download of quarantined 'pending' document must be blocked (HTTP 423 Locked)
        res_dl_pending = staff_client.get(f"/api/admissions/documents/{doc_pending_id}/download/", HTTP_HOST=self.DOMAIN)
        self.assertEqual(res_dl_pending.status_code, 423)
        self.assertIn("quarantined", res_dl_pending.data["error"].lower())

        # 6. Staff verification of 'pending' document must be blocked (HTTP 400 Bad Request)
        res_v_pending = staff_client.post(f"/api/admissions/documents/{doc_pending_id}/verify/", {}, HTTP_HOST=self.DOMAIN)
        self.assertEqual(res_v_pending.status_code, 400)
        self.assertIn("antivirus inspection state", res_v_pending.data["error"].lower())

        # 7. Staff download of quarantined 'infected' document must be blocked (HTTP 423 Locked)
        res_dl_infected = staff_client.get(f"/api/admissions/documents/{doc_infected_id}/download/", HTTP_HOST=self.DOMAIN)
        self.assertEqual(res_dl_infected.status_code, 423)
        self.assertIn("quarantined", res_dl_infected.data["error"].lower())

        # 8. Staff verification of 'infected' document must be blocked (HTTP 400 Bad Request)
        res_v_infected = staff_client.post(f"/api/admissions/documents/{doc_infected_id}/verify/", {}, HTTP_HOST=self.DOMAIN)
        self.assertEqual(res_v_infected.status_code, 400)

        # 9. Staff download of quarantined 'error' document must be blocked (HTTP 423 Locked)
        res_dl_error = staff_client.get(f"/api/admissions/documents/{doc_error_id}/download/", HTTP_HOST=self.DOMAIN)
        self.assertEqual(res_dl_error.status_code, 423)

        # 10. Staff download of 'clean' document must succeed with strict security headers (HTTP 200 OK)
        res_dl_clean = staff_client.get(f"/api/admissions/documents/{doc_clean_id}/download/", HTTP_HOST=self.DOMAIN)
        self.assertEqual(res_dl_clean.status_code, 200)
        self.assertIn("inline", res_dl_clean["Content-Disposition"])
        self.assertEqual(res_dl_clean["Cache-Control"], "no-store, no-cache, must-revalidate, private")
        self.assertEqual(res_dl_clean["Content-Security-Policy"], "default-src 'none'; sandbox")

        # 11. Staff verification of 'clean' document must succeed
        res_v_clean = staff_client.post(f"/api/admissions/documents/{doc_clean_id}/verify/", {}, HTTP_HOST=self.DOMAIN)
        self.assertEqual(res_v_clean.status_code, 200)
        self.assertEqual(res_v_clean.data["verification_status"], "verified")

    def test_applicant_document_download_authorization(self):
        """
        BLK-01 & Section 2.A: Verifies that applicant capability token authorization:
        - Allows downloading own clean documents via public and direct endpoints
        - Blocks downloading quarantined/unscanned documents (423 Locked)
        - Denies invalid capability tokens (404 Not Found)
        - Denies expired capability tokens (404 Not Found)
        - Denies revoked capability tokens (404 Not Found)
        - Denies cross-tenant download requests (404 Not Found)
        """
        import hashlib
        from datetime import timedelta
        from django.utils import timezone

        client = APIClient()

        raw_token = "applicant_token_secret_xyz123"
        token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()

        with tenant_context(self.school):
            app = AdmissionApplication.objects.create(
                application_number="APP-2026-APPLICANT-DL",
                first_name="Rani",
                last_name="Mukherjee",
                date_of_birth="2018-04-10",
                gender="female",
                guardian_first_name="Samir",
                guardian_last_name="Mukherjee",
                guardian_phone="+919876543299",
                academic_year="2026-27",
                academic_year_ref=self.academic_year,
                level=self.level_1,
                status="submitted",
                access_token_hash=token_hash,
                access_token_expires_at=timezone.now() + timedelta(days=90),
            )
            clean_doc = AdmissionDocument.objects.create(
                application=app,
                document_type="birth_certificate",
                title="Birth Certificate - Rani",
                file=SimpleUploadedFile("rani_birth.pdf", b"%PDF-1.4 rani content", content_type="application/pdf"),
                verification_status="pending",
                scan_status="clean",
                scan_details="Passed ClamAV antivirus inspection.",
            )
            quarantined_doc = AdmissionDocument.objects.create(
                application=app,
                document_type="previous_marksheet",
                title="Marksheet - Rani",
                file=SimpleUploadedFile("rani_marks.pdf", b"%PDF-1.4 marks content", content_type="application/pdf"),
                verification_status="pending",
                scan_status="pending",
            )
            clean_doc_id = str(clean_doc.id)
            quarantined_doc_id = str(quarantined_doc.id)

        # 1. Applicant download of clean document via public endpoint succeeds (HTTP 200 OK)
        res_pub_clean = client.get(
            f"/api/admissions/public/applications/APP-2026-APPLICANT-DL/documents/{clean_doc_id}/download/",
            HTTP_HOST=self.DOMAIN,
            HTTP_X_APPLICATION_TOKEN=raw_token,
        )
        self.assertEqual(res_pub_clean.status_code, 200)
        self.assertIn("inline", res_pub_clean["Content-Disposition"])

        # 2. Applicant download of clean document via direct document download endpoint succeeds with token header (HTTP 200 OK)
        res_direct_clean = client.get(
            f"/api/admissions/documents/{clean_doc_id}/download/",
            HTTP_HOST=self.DOMAIN,
            HTTP_X_APPLICATION_TOKEN=raw_token,
        )
        self.assertEqual(res_direct_clean.status_code, 200)

        # 3. Applicant download of quarantined document is blocked (HTTP 423 Locked)
        res_pub_quarantine = client.get(
            f"/api/admissions/public/applications/APP-2026-APPLICANT-DL/documents/{quarantined_doc_id}/download/",
            HTTP_HOST=self.DOMAIN,
            HTTP_X_APPLICATION_TOKEN=raw_token,
        )
        self.assertEqual(res_pub_quarantine.status_code, 423)

        # 4. Request with invalid capability token returns uniform 404 (anti-enumeration)
        res_bad_token = client.get(
            f"/api/admissions/public/applications/APP-2026-APPLICANT-DL/documents/{clean_doc_id}/download/",
            HTTP_HOST=self.DOMAIN,
            HTTP_X_APPLICATION_TOKEN="wrong_token_value",
        )
        self.assertEqual(res_bad_token.status_code, 404)

        # 5. Request with expired capability token returns 404
        with tenant_context(self.school):
            app.access_token_expires_at = timezone.now() - timedelta(days=1)
            app.save()

        res_expired = client.get(
            f"/api/admissions/public/applications/APP-2026-APPLICANT-DL/documents/{clean_doc_id}/download/",
            HTTP_HOST=self.DOMAIN,
            HTTP_X_APPLICATION_TOKEN=raw_token,
        )
        self.assertEqual(res_expired.status_code, 404)

        # 6. Request with revoked capability token returns 404
        with tenant_context(self.school):
            app.access_token_hash = ""
            app.save()

        res_revoked = client.get(
            f"/api/admissions/public/applications/APP-2026-APPLICANT-DL/documents/{clean_doc_id}/download/",
            HTTP_HOST=self.DOMAIN,
            HTTP_X_APPLICATION_TOKEN=raw_token,
        )
        self.assertEqual(res_revoked.status_code, 404)

        # 7. Cross-tenant download request on School 2 returns 404
        res_cross_tenant = client.get(
            f"/api/admissions/public/applications/APP-2026-APPLICANT-DL/documents/{clean_doc_id}/download/",
            HTTP_HOST="adm-test2.localhost",
            HTTP_X_APPLICATION_TOKEN=raw_token,
        )
        self.assertEqual(res_cross_tenant.status_code, 404)

    @override_settings(USE_X_ACCEL_REDIRECT=True, X_ACCEL_PREFIX="/protected_media/")
    def test_x_accel_redirect_mode(self):
        """
        BLK-01: Verifies Nginx X-Accel-Redirect accelerated internal media delivery.
        """
        staff_client = self._client_as(self.staff_user)

        with tenant_context(self.school):
            app = AdmissionApplication.objects.create(
                application_number="APP-2026-XACCEL-TEST",
                first_name="Vikram",
                last_name="Rao",
                date_of_birth="2018-09-09",
                gender="male",
                guardian_first_name="Mohan",
                guardian_last_name="Rao",
                guardian_phone="+919876543211",
                academic_year="2026-27",
                academic_year_ref=self.academic_year,
                level=self.level_1,
                status="documents_pending",
            )
            doc = AdmissionDocument.objects.create(
                application=app,
                document_type="birth_certificate",
                title="Birth Certificate - XAccel",
                file=SimpleUploadedFile("birth_xaccel.pdf", b"%PDF-1.4 sample content", content_type="application/pdf"),
                verification_status="pending",
                scan_status="clean",
            )
            doc_id = str(doc.id)

        res = staff_client.get(f"/api/admissions/documents/{doc_id}/download/", HTTP_HOST=self.DOMAIN)
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.has_header("X-Accel-Redirect"))
        self.assertTrue(res["X-Accel-Redirect"].startswith("/protected_media/admission_documents/"))
        self.assertEqual(res["Cache-Control"], "no-store, no-cache, must-revalidate, private")
        self.assertEqual(res["Content-Security-Policy"], "default-src 'none'; sandbox")
        # Body is not streamed by Django when X-Accel-Redirect is used
        self.assertEqual(res.content, b"")

    def test_antivirus_service_and_fail_closed_behavior(self):
        """
        BLK-04: Verifies antivirus scanner client stream interpretation and fail-closed handling.
        """
        from students.antivirus import scan_file_for_malware
        from students.admissions_tasks import scan_admission_document_task

        # 1. Clean file inspection simulation
        with patch("students.antivirus.socket.create_connection") as mock_conn:
            mock_sock = MagicMock()
            mock_sock.recv.side_effect = [b"stream: OK\0", b""]
            mock_conn.return_value.__enter__.return_value = mock_sock

            with override_settings(CLAMAV_ENABLED=True, CLAMAV_FAIL_CLOSED=True):
                dummy_file = io.BytesIO(b"%PDF-1.4 clean document bytes")
                is_clean, scan_status, scan_details = scan_file_for_malware(dummy_file, filename="test.pdf")
                self.assertTrue(is_clean)
                self.assertEqual(scan_status, "clean")
                self.assertIn("Passed ClamAV", scan_details)

        # 2. Infected file inspection simulation (EICAR / signature detection)
        with patch("students.antivirus.socket.create_connection") as mock_conn:
            mock_sock = MagicMock()
            mock_sock.recv.side_effect = [b"stream: Win.Test.EICAR_HDB-1 FOUND\0", b""]
            mock_conn.return_value.__enter__.return_value = mock_sock

            with override_settings(CLAMAV_ENABLED=True, CLAMAV_FAIL_CLOSED=True):
                dummy_file = io.BytesIO(b"X5O!P%@AP[4\\PZX54(P^)7CC)7}$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*")
                is_clean, scan_status, scan_details = scan_file_for_malware(dummy_file, filename="eicar.com")
                self.assertFalse(is_clean)
                self.assertEqual(scan_status, "infected")
                self.assertIn("Malware signature detected: Win.Test.EICAR_HDB-1", scan_details)

        # 3. Scanner connection failure / timeout must fail closed
        with patch("students.antivirus.socket.create_connection") as mock_conn:
            mock_conn.side_effect = ConnectionRefusedError("Connection refused to clamd on 127.0.0.1:3310")

            with override_settings(CLAMAV_ENABLED=True, CLAMAV_FAIL_CLOSED=True):
                dummy_file = io.BytesIO(b"%PDF-1.4 uninspected content")
                is_clean, scan_status, scan_details = scan_file_for_malware(dummy_file, filename="test.pdf")
                self.assertFalse(is_clean)
                self.assertEqual(scan_status, "error")
                self.assertIn("unreachable", scan_details.lower())

        # 4. Celery scan task execution in tenant schema
        with tenant_context(self.school):
            app = AdmissionApplication.objects.create(
                application_number="APP-2026-CELERY-TEST",
                first_name="Anita",
                last_name="Roy",
                date_of_birth="2018-02-02",
                gender="female",
                guardian_first_name="Biplab",
                guardian_last_name="Roy",
                guardian_phone="+919876543212",
                academic_year="2026-27",
                academic_year_ref=self.academic_year,
                level=self.level_1,
                status="documents_pending",
            )
            doc = AdmissionDocument.objects.create(
                application=app,
                document_type="birth_certificate",
                title="Birth Certificate - Celery Task",
                file=SimpleUploadedFile("birth_celery.pdf", b"%PDF-1.4 sample content", content_type="application/pdf"),
                verification_status="pending",
                scan_status="pending",
            )
            doc_id = str(doc.id)

        # Execute scan task with simulated clean scanner
        with patch("students.admissions_tasks.scan_file_for_malware") as mock_scan:
            mock_scan.return_value = (True, "clean", "Passed ClamAV antivirus inspection.")
            result = scan_admission_document_task(self.school.schema_name, doc_id)
            self.assertEqual(result["status"], "clean")

        with tenant_context(self.school):
            updated_doc = AdmissionDocument.objects.get(id=doc_id)
            self.assertEqual(updated_doc.scan_status, "clean")
            self.assertIsNotNone(updated_doc.scanned_at)

        # Idempotency check: running scan task again on clean doc skips work
        result2 = scan_admission_document_task(self.school.schema_name, doc_id)
        self.assertEqual(result2["status"], "already_scanned")

    def test_shared_redis_cache_and_throttling_settings(self):
        """
        BLK-02: Verifies Redis cache configuration and DRF scoped rate limit dictionary.
        """
        from django.conf import settings

        # Verify default cache backend is configured
        self.assertIn("default", settings.CACHES)
        default_cache = settings.CACHES["default"]
        # In test mode, it uses LocMemCache for test isolation; verify production points to Redis
        self.assertTrue(
            default_cache["BACKEND"].endswith("LocMemCache") or default_cache["BACKEND"].endswith("RedisCache")
        )

        # Verify all public admissions throttle scopes are defined in REST_FRAMEWORK
        rates = settings.REST_FRAMEWORK.get("DEFAULT_THROTTLE_RATES", {})
        expected_scopes = [
            "public_admissions_apply",
            "public_admissions_enquiry",
            "public_admissions_status",
            "public_admissions_upload",
            "public_admissions_info",
            "public_admissions_rotate",
        ]
        for scope in expected_scopes:
            self.assertIn(scope, rates, f"Missing DRF throttle scope: {scope}")

    def test_tls_and_security_headers_configuration(self):
        """
        BLK-03: Verifies transport security, trusted proxy handling, and security headers.
        """
        from django.conf import settings

        # Content protection headers
        self.assertTrue(settings.SECURE_CONTENT_TYPE_NOSNIFF)
        self.assertTrue(settings.SECURE_BROWSER_XSS_FILTER)
        self.assertEqual(settings.X_FRAME_OPTIONS, "DENY")
        self.assertEqual(settings.SECURE_REFERRER_POLICY, "same-origin")

        # Cookie security
        self.assertTrue(settings.SESSION_COOKIE_HTTPONLY)
        self.assertTrue(settings.CSRF_COOKIE_HTTPONLY)
        self.assertEqual(settings.SESSION_COOKIE_SAMESITE, "Lax")
        self.assertEqual(settings.CSRF_COOKIE_SAMESITE, "Lax")

        # HSTS safety: disabled by default (0) until HTTPS verified in staging/production
        self.assertEqual(settings.SECURE_HSTS_SECONDS, 0)



