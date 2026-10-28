import datetime
import io
import uuid
from decimal import Decimal

from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection
from django.test import TransactionTestCase
from django_tenants.utils import tenant_context
from rest_framework.test import APIClient

from academics.models import AcademicLevel, AcademicYear, Program, Section
from accounts.models import User
from families.models import Parent, StudentParentRelation
from fees.models import FeeHead, StudentFee
from organizations.models import Domain, Organization
from roles.models import Role, UserRole
from staff.models import Instructor, StaffMember
from students.models import Student

STUDENT_HEADER = "admission_no,first_name,last_name,gender,date_of_birth,class,section,father_name,father_phone,mother_name,mother_phone\n"


def csv_file(text, name="data.csv"):
    return SimpleUploadedFile(name, text.encode("utf-8"), content_type="text/csv")


class BulkImportTests(TransactionTestCase):
    SCHEMA, DOMAIN = "import_school", "import.localhost"

    def setUp(self):
        connection.set_schema_to_public()
        self.school = Organization.objects.create(schema_name=self.SCHEMA, name="Import School")
        Domain.objects.create(domain=self.DOMAIN, tenant=self.school, is_primary=True)
        self.owner = User.objects.create_user(username="imp_owner", email="imp@x.test", password="Pass1234!")
        self.clerk = User.objects.create_user(username="imp_clerk", email="clerk@x.test", password="Pass1234!")
        with tenant_context(self.school):
            role, _ = Role.objects.get_or_create(slug="owner", defaults={"name": "Owner", "is_system_role": True})
            UserRole.objects.create(user=self.owner, role=role)
            UserRole.objects.create(user=self.clerk, role=Role.objects.create(name="Clerk", slug="imp-clerk"))
            AcademicYear.objects.create(name="2026-27", start_date=datetime.date(2026, 4, 1),
                                        end_date=datetime.date(2027, 3, 31), is_current=True)
            program = Program.objects.create(name="School", code="SCH")
            self.level = AcademicLevel.objects.create(program=program, name="Class 5", order=5)
            Section.objects.create(level=self.level, name="A", capacity=40)
            FeeHead.objects.get_or_create(name="Tuition")

    def tearDown(self):
        connection.set_schema_to_public()
        self.school.delete(force_drop=True)
        User.objects.filter(username__in=["imp_owner", "imp_clerk"]).delete()

    def _client(self, username="imp_owner"):
        client = APIClient()
        assert client.post("/api/auth/login/", {"username": username, "password": "Pass1234!"},
                           HTTP_HOST=self.DOMAIN).status_code == 200
        return client

    def _upload(self, kind, file, confirm=False, client=None):
        return (client or self._client()).post(f"/api/imports/{kind}/", {"file": file, "confirm": "true" if confirm else ""},
                                               format="multipart", HTTP_HOST=self.DOMAIN)

    def test_templates_download_as_excel(self):
        client = self._client()
        for kind in ("students", "staff", "opening-fees"):
            response = client.get(f"/api/imports/{kind}/template/", HTTP_HOST=self.DOMAIN)
            self.assertEqual(response.status_code, 200, kind)
            self.assertTrue(response.content.startswith(b"PK"))  # .xlsx is a zip

    def test_students_preview_saves_nothing_then_confirm_saves_with_shared_parents(self):
        data = STUDENT_HEADER + (
            "ADM-1,Aarav,Sharma,M,15-06-2015,Class 5,A,Rajesh Sharma,98765 43210,Priya Sharma,9876543211\n"
            "ADM-2,Anaya,Sharma,F,02/01/2017,class 5,,Rajesh Sharma,+91 9876543210,,\n"
        )
        preview = self._upload("students", csv_file(data))
        self.assertEqual(preview.status_code, 200, preview.data)
        self.assertEqual((preview.data["rows"], preview.data["error_count"], preview.data["saved"]), (2, 0, 0))
        with tenant_context(self.school):
            self.assertFalse(Student.objects.exists())
        saved = self._upload("students", csv_file(data), confirm=True)
        self.assertEqual(saved.status_code, 201, saved.data)
        with tenant_context(self.school):
            self.assertEqual(Student.objects.count(), 2)
            father = Parent.objects.get(profile__phone="9876543210")
            self.assertEqual(StudentParentRelation.objects.filter(parent=father).count(), 2)  # siblings share
            self.assertEqual(Parent.objects.count(), 2)
            aarav = Student.objects.get(enrollment_id="ADM-1")
            self.assertEqual(aarav.profile.date_of_birth, datetime.date(2015, 6, 15))
            self.assertEqual(aarav.enrollments.get(is_current=True).section.name, "A")

    def test_any_bad_row_means_nothing_is_saved(self):
        data = STUDENT_HEADER + (
            "ADM-1,Good,Row,M,15-06-2015,Class 5,A,Dad,9876543210,,\n"
            "ADM-1,Dup,Number,F,31-02-2015,Class 9,Z,,,,\n"
        )
        response = self._upload("students", csv_file(data), confirm=True)
        self.assertEqual(response.status_code, 400)
        columns = {(e["row"], e["column"]) for e in response.data["errors"]}
        self.assertTrue({(3, "admission_no"), (3, "date_of_birth"), (3, "class"), (3, "father_phone")} <= columns)
        with tenant_context(self.school):
            self.assertFalse(Student.objects.exists())

    def test_excel_upload_with_real_excel_dates(self):
        from openpyxl import Workbook

        book = Workbook()
        sheet = book.active
        sheet.append(["first_name", "gender", "date_of_birth", "class", "mother_name", "mother_phone"])
        sheet.append(["Diya", "Female", datetime.datetime(2016, 3, 9), "Class 5", "Meena", 9123456789])
        out = io.BytesIO()
        book.save(out)
        upload = SimpleUploadedFile("students.xlsx", out.getvalue())
        response = self._upload("students", upload, confirm=True)
        self.assertEqual(response.status_code, 201, response.data)
        with tenant_context(self.school):
            diya = Student.objects.get(profile__first_name="Diya")
            self.assertEqual(diya.profile.date_of_birth, datetime.date(2016, 3, 9))
            self.assertTrue(diya.enrollment_id.startswith("STD-"))

    def test_staff_import_makes_teachers_assignable(self):
        data = ("employee_id,first_name,last_name,designation,is_teacher,subject_specialization,phone\n"
                "EMP-1,Sunita,Rao,Teacher,Yes,Mathematics,9812345678\n"
                "EMP-2,Ravi,Kumar,Accountant,No,,\n")
        response = self._upload("staff", csv_file(data), confirm=True)
        self.assertEqual(response.status_code, 201, response.data)
        with tenant_context(self.school):
            # Only the imported people (the school's owner already has a staff record of their own).
            self.assertEqual(StaffMember.objects.filter(employee_id__in=["EMP-1", "EMP-2"]).count(), 2)
            self.assertEqual(Instructor.objects.get(staff_member__employee_id="EMP-1").specialization, "Mathematics")
            self.assertFalse(Instructor.objects.filter(staff_member__employee_id="EMP-2").exists())
        again = self._upload("staff", csv_file(data), confirm=True)
        self.assertEqual(again.status_code, 400)  # employee IDs now taken

    def test_opening_fee_balances(self):
        self._upload("students", csv_file(STUDENT_HEADER + "ADM-1,Aarav,Sharma,M,15-06-2015,Class 5,A,Dad,9876543210,,\n"),
                     confirm=True)
        data = "admission_no,fee_head,amount_due,due_date\nADM-1,tuition,\"12,500\",30-04-2026\nADM-404,Tuition,100,\n"
        bad = self._upload("opening-fees", csv_file(data), confirm=True)
        self.assertEqual(bad.status_code, 400)
        self.assertEqual(bad.data["errors"][0]["row"], 3)
        good = self._upload("opening-fees", csv_file(data.rsplit("ADM-404", 1)[0]), confirm=True)
        self.assertEqual(good.status_code, 201, good.data)
        with tenant_context(self.school):
            fee = StudentFee.objects.get()
            self.assertEqual((fee.amount_due, fee.academic_year), (Decimal("12500.00"), "2026-27"))

    def test_needs_the_permission(self):
        clerk = self._client("imp_clerk")
        self.assertEqual(self._upload("students", csv_file(STUDENT_HEADER), client=clerk).status_code, 403)
        self.assertEqual(clerk.get("/api/imports/staff/template/", HTTP_HOST=self.DOMAIN).status_code, 403)

    def test_wrong_file_type_and_missing_columns(self):
        response = self._upload("students", SimpleUploadedFile("photo.png", b"\x89PNG"))
        self.assertEqual(response.status_code, 400)
        response = self._upload("students", csv_file("first_name,gender\nA,M\n"))
        self.assertIn("Columns missing", response.data["error"])

    def test_the_plan_student_limit_is_respected(self):
        from billing.models import Plan, Subscription

        plan = Plan.objects.create(code=f"imp-{uuid.uuid4().hex[:6]}", name="Tiny", monthly_price=Decimal("1.00"),
                                   student_limit=1)
        Subscription.objects.create(organization=self.school, plan=plan, cycle="monthly", status="trial",
                                    trial_ends_at=datetime.datetime(2099, 1, 1, tzinfo=datetime.timezone.utc))
        try:
            data = STUDENT_HEADER + ("A1,One,X,M,01-01-2015,Class 5,,Dad,9876543210,,\n"
                                     "A2,Two,X,M,01-01-2015,Class 5,,Dad,9876543210,,\n")
            response = self._upload("students", csv_file(data), confirm=True)
            self.assertEqual(response.status_code, 400)
            self.assertIn("allows 1", response.data["error"])
            with tenant_context(self.school):
                self.assertFalse(Student.objects.exists())
        finally:
            connection.set_schema_to_public()
            Subscription.objects.filter(organization=self.school).delete()
            plan.delete()
